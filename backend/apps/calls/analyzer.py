from .models import ScriptTemplate, ScriptStep, CallAnalysis


class PlaceholderAnalyzer:
    """
    Placeholder analyzer that does keyword-based script compliance checking
    without a real ASR/NLP backend.
    """

    def analyze(self, call, language_hint='ru'):
        transcript = f"(ASR not configured) - Demo transcript for call {call.id}"

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
            'name': client.name if client else '',
            'phone': client.primary_phone if client else '',
            'gender': client.gender if client else 'unknown',
            'language': language_hint,
            'reason': f'Inquiry from call {call.id}',
            'result': 'pending_analysis',
            'notes': f'Auto-generated from call {call.id}',
            'tags': [],
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
            'summary_short': summary_short,
            'summary_structured': summary_structured,
            'client_draft': client_draft,
            'operator_coaching': operator_coaching,
            'script_compliance': script_compliance,
            'model_info': model_info,
        }
