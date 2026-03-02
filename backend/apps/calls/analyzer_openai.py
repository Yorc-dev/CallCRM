import json
import re

from django.conf import settings

from .models import ScriptTemplate, CallRecording


class OpenAIAnalyzer:
    """
    Analyzer that uses OpenAI APIs for transcription (Whisper) and structured
    insights (chat completion).  Falls back gracefully if any optional fields
    are missing from the LLM response.
    """

    # Reuse phone/name patterns from PlaceholderAnalyzer for client_draft fallback
    _PHONE_RE = re.compile(
        r'(\+?[78]\d{10}|\+?[78][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})'
    )
    _NAME_RE = re.compile(
        r'(?:говорит|меня зовут|это|клиент|зовут)\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*)',
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        digits = re.sub(r'\D', '', raw)
        if len(digits) == 11 and digits[0] in ('7', '8'):
            return '+7' + digits[1:]
        return '+' + digits if digits else raw

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        import openai
        return openai.OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT_SEC,
        )

    def _transcribe(self, openai_client, recording: CallRecording, language: str) -> str:
        """Send audio file to Whisper and return transcript text."""
        with recording.file.open('rb') as audio_fp:
            response = openai_client.audio.transcriptions.create(
                model=settings.OPENAI_TRANSCRIBE_MODEL,
                file=audio_fp,
                language=language,
                response_format='text',
            )
        # response is a plain string when response_format='text'
        return response if isinstance(response, str) else str(response)

    def _generate_insights(self, openai_client, transcript: str, language: str) -> tuple:
        """Call chat completion to produce structured analysis."""
        system_prompt = (
            "You are an expert call-center quality analyst. "
            "Analyze the provided call transcript and return a JSON object with the following keys:\n"
            "  summary_short  – one sentence (string)\n"
            "  summary_structured – object with keys: category (string), key_phrases (array of strings), "
            "topic (string)\n"
            "  category – string label for the call topic (e.g. 'complaint', 'inquiry', 'sales')\n"
            "  operator_coaching – object with keys: advice (array of strings), score (integer 0-100)\n"
            "  client_draft – object with keys: name (string), phone (string), "
            f"language ('{language}'), notes (string)\n"
            "Return ONLY the JSON object, no additional text."
        )
        response = openai_client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': transcript},
            ],
            response_format={'type': 'json_object'},
        )
        content = response.choices[0].message.content
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        usage = response.usage
        return parsed, {
            'prompt_tokens': usage.prompt_tokens if usage else None,
            'completion_tokens': usage.completion_tokens if usage else None,
        }

    # ------------------------------------------------------------------
    # Script compliance (deterministic, same logic as PlaceholderAnalyzer)
    # ------------------------------------------------------------------

    def _compute_script_compliance(self, transcript: str, language_hint: str):
        template = (
            ScriptTemplate.objects.filter(is_default=True, language=language_hint)
            .prefetch_related('steps')
            .first()
        )
        if not template:
            template = (
                ScriptTemplate.objects.filter(is_default=True)
                .prefetch_related('steps')
                .first()
            )

        script_compliance = {}
        found_steps = 0
        total_required = 0
        missing_required = []

        if template:
            for step in template.steps.all():
                keywords = step.keywords or []
                matched = any(kw.lower() in transcript.lower() for kw in keywords)
                script_compliance[step.key] = matched
                if step.required:
                    total_required += 1
                    if matched:
                        found_steps += 1
                    else:
                        missing_required.append(step.key)

        script_score = (found_steps / total_required * 100) if total_required > 0 else 0.0
        return script_compliance, round(script_score, 2), template, missing_required

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def analyze(self, call, language_hint: str = 'ru') -> dict:
        # Normalize kz → kk
        if language_hint == 'kz':
            language_hint = 'kk'

        # 1. Load latest recording
        recording = (
            CallRecording.objects.filter(call=call)
            .order_by('-uploaded_at')
            .first()
        )
        if not recording:
            raise ValueError(f'No recording found for call {call.id}')

        openai_client = self._get_client()

        # 2. Transcribe
        transcript = self._transcribe(openai_client, recording, language_hint)

        # 3. Script compliance (deterministic keyword matching)
        script_compliance, script_score, template, _missing = (
            self._compute_script_compliance(transcript, language_hint)
        )

        # 4. AI insights
        insights, token_usage = self._generate_insights(openai_client, transcript, language_hint)

        # 5. Build client_draft from AI response, fall back to regex extraction
        client_draft = insights.get('client_draft') or {}
        if not client_draft.get('phone'):
            phone_match = self._PHONE_RE.search(transcript)
            if phone_match:
                client_draft['phone'] = self._normalize_phone(phone_match.group(1))
        if not client_draft.get('name'):
            name_match = self._NAME_RE.search(transcript)
            if name_match:
                client_draft['name'] = name_match.group(1).strip()
            elif call.client:
                client_draft['name'] = call.client.name
        if not client_draft.get('phone') and call.client:
            client_draft['phone'] = call.client.primary_phone
        client_draft.setdefault('language', language_hint)
        client_draft.setdefault('notes', f'Auto-generated from call {call.id}')

        # 6. Build model_info
        model_info = {
            'analyzer': 'openai_v1',
            'transcribe_model': settings.OPENAI_TRANSCRIBE_MODEL,
            'chat_model': settings.OPENAI_CHAT_MODEL,
            'script_template': template.name if template else None,
            'script_version': template.version if template else None,
            'token_usage': token_usage,
        }

        return {
            'asr_language': language_hint,
            'transcript_text': transcript,
            'summary_short': insights.get('summary_short', ''),
            'summary_structured': insights.get('summary_structured', {}),
            'category': insights.get('category', ''),
            'operator_coaching': insights.get('operator_coaching', {}),
            'client_draft': client_draft,
            'script_compliance': script_compliance,
            'script_score': script_score,
            'model_info': model_info,
        }
