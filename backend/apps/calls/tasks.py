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
    5. Create/update Client from client_draft and link to call
    6. Set status=done
    On exception: set status=failed, re-raise
    """
    Call = apps.get_model('calls', 'Call')
    CallAnalysis = apps.get_model('calls', 'CallAnalysis')
    Client = apps.get_model('calls', 'Client')
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

        # Auto-create or update Client from extracted draft fields
        draft = result.get('client_draft', {})
        phone = (draft.get('phone') or '').strip()
        name = (draft.get('name') or '').strip()
        lang = draft.get('language', 'ru')
        if lang == 'kz':
            lang = 'kk'
        notes = (draft.get('notes') or '').strip()

        if phone:
            client, _ = Client.objects.get_or_create(primary_phone=phone)
        else:
            client = Client.objects.create(primary_phone='', tags=['unknown_phone'])

        if name:
            client.name = name
        if lang in ('ru', 'kk'):
            client.language_hint = lang
        if notes:
            tags = list(client.tags or [])
            if notes not in tags:
                tags.append(notes)
            client.tags = tags
        client.save()

        call.client = client
        call.status = Call.STATUS_DONE
        call.save(update_fields=['client', 'status'])

        return {'call_id': call_id, 'status': 'done'}

    except Exception as exc:
        call.status = Call.STATUS_FAILED
        call.save(update_fields=['status'])
        raise
