from celery import shared_task
from django.apps import apps


@shared_task(bind=True)
def analyze_call(self, call_id, language_hint='ru', script_version='v1'):
    """
    Celery task to analyze a call recording.
    1. Get call, set status=processing
    2. Get or create CallAnalysis
    3. Run PlaceholderAnalyzer
    4. Save analysis
    5. Set status=done
    On exception: set status=failed, re-raise
    """
    Call = apps.get_model('calls', 'Call')
    CallAnalysis = apps.get_model('calls', 'CallAnalysis')
    from apps.calls.analyzer import PlaceholderAnalyzer

    call = Call.objects.select_related('client', 'operator').get(pk=call_id)
    call.status = Call.STATUS_PROCESSING
    call.save(update_fields=['status'])

    try:
        analyzer = PlaceholderAnalyzer()
        result = analyzer.analyze(call, language_hint=language_hint)

        analysis, _ = CallAnalysis.objects.get_or_create(call=call)
        for field, value in result.items():
            setattr(analysis, field, value)
        analysis.save()

        call.status = Call.STATUS_DONE
        call.save(update_fields=['status'])

        return {'call_id': call_id, 'status': 'done'}

    except Exception as exc:
        call.status = Call.STATUS_FAILED
        call.save(update_fields=['status'])
        raise
