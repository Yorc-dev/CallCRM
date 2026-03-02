import hashlib
import logging

import requests as http_requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

from apps.calls.models import Call, Client, CallRecording
from apps.calls.tasks import analyze_call as analyze_call_task

logger = logging.getLogger(__name__)


def _parse_operator_mapping():
    """
    Parse TWILIO_OPERATOR_MAPPING setting into an ordered list of
    (username, phone) tuples.  Falls back to TWILIO_OPERATOR_NUMBERS
    (phone-only, no username) when the mapping is empty.
    """
    mapping_str = getattr(settings, 'TWILIO_OPERATOR_MAPPING', '')
    if mapping_str:
        result = []
        for pair in mapping_str.split(','):
            pair = pair.strip()
            if '=' in pair:
                username, phone = pair.split('=', 1)
                result.append((username.strip(), phone.strip()))
        if result:
            return result

    # Fall back to TWILIO_OPERATOR_NUMBERS (no username)
    numbers_str = getattr(settings, 'TWILIO_OPERATOR_NUMBERS', '')
    return [(None, n.strip()) for n in numbers_str.split(',') if n.strip()]


def _validate_twilio_signature(request):
    """
    Return True if the request carries a valid Twilio signature,
    or if TWILIO_AUTH_TOKEN is not configured (dev/test mode).
    """
    auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    if not auth_token:
        return True  # skip validation when token not configured

    signature = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
    base_url = getattr(settings, 'TWILIO_WEBHOOK_BASE_URL', '').rstrip('/')
    url = base_url + request.path
    params = request.POST.dict()

    validator = RequestValidator(auth_token)
    return validator.validate(url, params, signature)


def _get_language_hint(call):
    """
    Return the ASR language hint for *call*.
    Uses client.language_hint when available, falls back to
    TWILIO_DEFAULT_LANG (default 'ru').  Normalises 'kz' -> 'kk'.
    """
    default_lang = getattr(settings, 'TWILIO_DEFAULT_LANG', 'ru')
    if call.client:
        lang = call.client.language_hint or default_lang
    else:
        lang = default_lang
    if lang == 'kz':
        lang = 'kk'
    return lang


def _build_dial_twiml(call, operators, attempt):
    """
    Return a TwiML ``<Response>`` string that dials operator at *attempt*
    index with recording enabled.
    """
    base_url = getattr(settings, 'TWILIO_WEBHOOK_BASE_URL', '').rstrip('/')
    username, phone = operators[attempt]

    resp = VoiceResponse()
    dial = resp.dial(
        record='record-from-answer',
        recording_status_callback=f'{base_url}/api/twilio/voice/recording/',
        recording_status_callback_method='POST',
        action=(
            f'{base_url}/api/twilio/voice/status/'
            f'?call_id={call.pk}&attempt={attempt}'
        ),
        method='POST',
        timeout=20,
    )
    dial.number(phone)
    return str(resp)


class TwilioInboundCallView(APIView):
    """
    POST /api/twilio/voice/inbound/

    Entry point for inbound calls from Twilio.
    - Validates Twilio signature.
    - Creates/finds Client by caller's phone number.
    - Creates Call record (status=new).
    - Returns TwiML to dial the first operator (hunt-group).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        if not _validate_twilio_signature(request):
            return HttpResponse('Forbidden', status=403)

        call_sid = request.POST.get('CallSid', '')
        from_phone = request.POST.get('From', '')
        to_phone = request.POST.get('To', '')

        # Find or create the calling Client
        client = None
        if from_phone:
            client, _ = Client.objects.get_or_create(primary_phone=from_phone)

        operators = _parse_operator_mapping()
        if not operators:
            resp = VoiceResponse()
            resp.say('No operators configured. Please try again later.')
            resp.hangup()
            return HttpResponse(str(resp), content_type='text/xml')

        # Resolve operator User for the first operator (best-effort)
        from django.contrib.auth import get_user_model
        User = get_user_model()

        operator = None
        for uname, _ in operators:
            if uname:
                operator = User.objects.filter(username=uname).first()
                if operator:
                    break
        if operator is None:
            operator = User.objects.filter(is_superuser=True).first()
        if operator is None:
            resp = VoiceResponse()
            resp.say('Service unavailable. Please try again later.')
            resp.hangup()
            return HttpResponse(str(resp), content_type='text/xml')

        call = Call.objects.create(
            client=client,
            operator=operator,
            call_datetime=timezone.now(),
            status=Call.STATUS_NEW,
            external_call_id=call_sid or None,
            from_phone=from_phone or None,
            to_phone=to_phone or None,
        )

        twiml = _build_dial_twiml(call, operators, attempt=0)
        return HttpResponse(twiml, content_type='text/xml')


class TwilioDialStatusView(APIView):
    """
    POST /api/twilio/voice/status/?call_id=<id>&attempt=<n>

    Twilio calls this URL when a dialled leg ends (the <Dial> action URL).
    - If the operator answered (DialCallStatus=completed): do nothing; the
      recording callback will ingest the audio.
    - Otherwise: try the next operator in the hunt-group.
    - If all operators exhausted: mark call as failed.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        if not _validate_twilio_signature(request):
            return HttpResponse('Forbidden', status=403)

        call_id = request.GET.get('call_id')
        attempt = int(request.GET.get('attempt', 0))
        dial_status = request.POST.get('DialCallStatus', '')

        try:
            call = Call.objects.select_related('client').get(pk=call_id)
        except (Call.DoesNotExist, ValueError, TypeError):
            logger.warning('TwilioDialStatusView: call %s not found', call_id)
            return HttpResponse('<Response></Response>', content_type='text/xml')

        # Update operator field to whomever was dialled this attempt
        operators = _parse_operator_mapping()
        if 0 <= attempt < len(operators):
            uname, _ = operators[attempt]
            if uname:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.filter(username=uname).first()
                if user and dial_status == 'completed':
                    call.operator = user
                    call.save(update_fields=['operator'])

        if dial_status == 'completed':
            # Operator answered; recording callback will handle the rest.
            return HttpResponse('<Response></Response>', content_type='text/xml')

        # Operator did not answer – try next in hunt-group
        next_attempt = attempt + 1
        if next_attempt < len(operators):
            twiml = _build_dial_twiml(call, operators, attempt=next_attempt)
            return HttpResponse(twiml, content_type='text/xml')

        # All operators tried and none answered
        call.status = Call.STATUS_FAILED
        call.save(update_fields=['status'])

        resp = VoiceResponse()
        resp.say('Sorry, no operators are available. Please try again later.')
        resp.hangup()
        return HttpResponse(str(resp), content_type='text/xml')


class TwilioRecordingCallbackView(APIView):
    """
    POST /api/twilio/voice/recording/

    Twilio calls this URL when a recording is ready.
    - Downloads the recording from Twilio.
    - Creates a CallRecording linked to the matching Call.
    - Enqueues the analysis task with the appropriate language hint.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        if not _validate_twilio_signature(request):
            return HttpResponse('Forbidden', status=403)

        call_sid = request.POST.get('CallSid', '')
        recording_sid = request.POST.get('RecordingSid', '')
        recording_status = request.POST.get('RecordingStatus', '')

        if recording_status and recording_status != 'completed':
            # Not yet ready; ignore
            return HttpResponse('', status=204)

        try:
            call = Call.objects.select_related('client').get(external_call_id=call_sid)
        except Call.DoesNotExist:
            logger.warning(
                'TwilioRecordingCallbackView: no Call for CallSid %s', call_sid
            )
            return HttpResponse('', status=204)

        if recording_sid:
            call.external_recording_id = recording_sid
            call.save(update_fields=['external_recording_id'])

            # Build the download URL from the fixed Twilio API domain and the
            # recording SID, rather than trusting the user-supplied RecordingUrl,
            # to prevent SSRF.
            account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
            auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
            if account_sid:
                mp3_url = (
                    f'https://api.twilio.com/2010-04-01/Accounts/'
                    f'{account_sid}/Recordings/{recording_sid}.mp3'
                )
                auth = (account_sid, auth_token) if auth_token else None

                try:
                    resp = http_requests.get(mp3_url, auth=auth, timeout=60)
                    resp.raise_for_status()
                except Exception:
                    logger.exception(
                        'TwilioRecordingCallbackView: failed to download recording %s',
                        recording_sid,
                    )
                    return HttpResponse('', status=204)

                audio_bytes = resp.content
                sha256_hex = hashlib.sha256(audio_bytes).hexdigest()
                file_name = f'twilio_{recording_sid}.mp3'

                CallRecording.objects.create(
                    call=call,
                    file=ContentFile(audio_bytes, name=file_name),
                    mime_type='audio/mpeg',
                    size_bytes=len(audio_bytes),
                    sha256=sha256_hex,
                )

                call.status = Call.STATUS_UPLOADED
                call.save(update_fields=['status'])

                language_hint = _get_language_hint(call)
                analyze_call_task.delay(call.pk, language_hint=language_hint)

        return HttpResponse('', status=204)
