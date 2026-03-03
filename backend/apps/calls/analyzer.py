import re

from .models import ScriptTemplate, ScriptStep, CallAnalysis


class PlaceholderAnalyzer:
    """
    Placeholder analyzer that does keyword-based script compliance checking
    without a real ASR/NLP backend.
    """

    # Simple heuristics to extract phone and name from transcript text
    _PHONE_RE = re.compile(r'(\+?[78]\d{10}|\+?[78][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})')
    # Matches Russian names following phrases like "говорит", "меня зовут", etc.
    # Captures one or more space-separated capitalized Cyrillic words.
    _NAME_RE = re.compile(
        r'(?:говорит|меня зовут|это|клиент|зовут)\s+([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)*)',
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        """Strip spaces/dashes and normalise to +7XXXXXXXXXX format."""
        digits = re.sub(r'\D', '', raw)
        if len(digits) == 11 and digits[0] in ('7', '8'):
            return '+7' + digits[1:]
        return '+' + digits if digits else raw

    def analyze(self, call, language_hint='ru'):
        # Demo transcript includes extractable name/phone so the flow can be demoed
        transcript = (
            f"(ASR not configured) - Demo transcript for call {call.id}. "
            f"Говорит Иван Петров. Телефон: +77001234567."
        )

        # Attempt to extract phone and name via regex
        phone_match = self._PHONE_RE.search(transcript)
        extracted_phone = self._normalize_phone(phone_match.group(1)) if phone_match else ''

        name_match = self._NAME_RE.search(transcript)
        extracted_name = name_match.group(1).strip() if name_match else ''

        # Get default script template matching the language
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
            steps = list(template.steps.all())
            for step in steps:
                keywords = step.keywords or []
                matched = any(kw.lower() in transcript.lower() for kw in keywords)
                script_compliance[step.key] = matched
                if step.required:
                    total_required += 1
                    if matched:
                        found_steps += 1
                    else:
                        missing_required.append(step.key)

        script_score = (found_steps / total_required) if total_required > 0 else 0.0
        duration = call.duration_sec or 0
        total_steps = len(script_compliance)

        summary_short = (
            f"Call analyzed. Duration: {duration}s. "
            f"Steps found: {found_steps}/{total_required}."
        )

        summary_structured = {
            'category': call.category or 'unknown',
            'key_phrases': [],
            'duration': duration,
            'language': language_hint,
            'script_score': round(script_score, 2),
        }

        # Coaching advice for missing steps
        advice = []
        step_advice = {
            'greeting': 'Start the call with a proper greeting.',
            'name_ask': 'Ask for the client\'s name early in the conversation.',
            'confirmation': 'Confirm key details with the client.',
            'need_identification': 'Clarify what the client needs help with.',
            'solution_offer': 'Offer a clear solution or next step.',
            'deadline': 'Set a deadline or timeframe for resolution.',
            'closing': 'Close the call professionally with a farewell.',
        }
        for key in missing_required:
            if key in step_advice:
                advice.append(step_advice[key])
            else:
                advice.append(f'Complete the "{key}" step in your script.')

        operator_coaching = {'advice': advice, 'score': round(script_score, 2)}

        client = call.client
        client_draft = {
            'name': extracted_name or (client.name if client else ''),
            'phone': extracted_phone or (client.primary_phone if client else ''),
            'language': language_hint,
            'gender': 'unknown',
            'notes': f'Auto-generated from call {call.id}',
        }

        model_info = {
            'analyzer': 'placeholder_v1',
            'version': '1.0.0',
            'script_template': template.name if template else None,
            'script_version': template.version if template else None,
        }

        return {
            'asr_language': language_hint,
            'transcript_text': transcript,
            'transcript_dialogue': [],
            'summary_short': summary_short,
            'summary_structured': summary_structured,
            'client_draft': client_draft,
            'operator_coaching': operator_coaching,
            'script_compliance': script_compliance,
            'script_score': script_score,
            'model_info': model_info,
        }
