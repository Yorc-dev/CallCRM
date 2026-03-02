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
    5. Auto-create/update Client from client_draft and attach to call
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

        # Auto-create or update Client from client_draft and attach to call
        if not call.client:
            draft = result.get('client_draft', {})
            phone = (draft.get('phone') or '').strip()
            name = draft.get('name', '')
            gender = draft.get('gender', Client.GENDER_UNKNOWN)
            if gender not in (Client.GENDER_MALE, Client.GENDER_FEMALE, Client.GENDER_UNKNOWN):
                gender = Client.GENDER_UNKNOWN
            extra_tags = [t for t in (draft.get('tags') or []) if t]

            if phone:
                client, created = Client.objects.get_or_create(
                    primary_phone=phone,
                    defaults={
                        'name': name,
                        'gender': gender,
                        'tags': extra_tags,
                    },
                )
                if not created:
                    if name and not client.name:
                        client.name = name
                    if gender != Client.GENDER_UNKNOWN:
                        client.gender = gender
                    client.save()
            else:
                client = Client.objects.create(
                    primary_phone='',
                    name=name,
                    gender=gender,
                    tags=['unknown_phone'] + extra_tags,
                )

            call.client = client
            call.save(update_fields=['client'])

        call.status = Call.STATUS_DONE
        call.save(update_fields=['status'])

        return {'call_id': call_id, 'status': 'done'}

    except Exception as exc:
        call.status = Call.STATUS_FAILED
        call.save(update_fields=['status'])
        raise
