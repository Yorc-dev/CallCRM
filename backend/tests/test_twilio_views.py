"""
Tests for the telephony_twilio integration:
  - POST /api/twilio/voice/inbound/
  - POST /api/twilio/voice/status/
  - POST /api/twilio/voice/recording/
"""
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.calls.models import Call, Client, CallRecording

OPERATOR_MAPPING = 'Sultan=+996222021103,katana=+996702110333'

TWILIO_SETTINGS = dict(
    TWILIO_ACCOUNT_SID='ACtest123',
    TWILIO_AUTH_TOKEN='',  # empty → skip signature validation
    TWILIO_WEBHOOK_BASE_URL='http://testserver',
    TWILIO_DEFAULT_LANG='ru',
    TWILIO_OPERATOR_MAPPING=OPERATOR_MAPPING,
    TWILIO_OPERATOR_NUMBERS='',
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    MEDIA_ROOT='/tmp/test_twilio_media/',
)


def _inbound_url():
    return reverse('twilio-inbound')


def _status_url(call_id, attempt=0):
    return reverse('twilio-dial-status') + f'?call_id={call_id}&attempt={attempt}'


def _recording_url():
    return reverse('twilio-recording')


@override_settings(**TWILIO_SETTINGS)
class TwilioInboundCallViewTest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        # Create operator users matching the mapping
        self.sultan = User.objects.create_user(
            username='Sultan', password='x', role='operator', phone='+996222021103'
        )
        self.katana = User.objects.create_user(
            username='katana', password='x', role='operator', phone='+996702110333'
        )

    def _post(self, data=None):
        payload = {
            'CallSid': 'CAtest001',
            'From': '+77001234567',
            'To': '+996123456789',
        }
        if data:
            payload.update(data)
        return self.client_api.post(_inbound_url(), payload)

    def test_creates_client_and_call(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Dial', resp.content)
        self.assertIn(b'+996222021103', resp.content)  # first operator dialled

        call = Call.objects.get(external_call_id='CAtest001')
        self.assertEqual(call.status, Call.STATUS_NEW)
        self.assertEqual(call.from_phone, '+77001234567')
        self.assertEqual(call.to_phone, '+996123456789')

        client = Client.objects.get(primary_phone='+77001234567')
        self.assertEqual(call.client, client)

    def test_content_type_xml(self):
        resp = self._post()
        self.assertIn('xml', resp['Content-Type'])

    def test_no_operators_returns_say(self):
        with self.settings(TWILIO_OPERATOR_MAPPING='', TWILIO_OPERATOR_NUMBERS=''):
            resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'No operators configured', resp.content)

    def test_returns_403_on_bad_signature(self):
        with self.settings(TWILIO_AUTH_TOKEN='real-token'):
            resp = self._post()
        self.assertEqual(resp.status_code, 403)


@override_settings(**TWILIO_SETTINGS)
class TwilioDialStatusViewTest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.sultan = User.objects.create_user(
            username='Sultan', password='x', role='operator'
        )
        self.katana = User.objects.create_user(
            username='katana', password='x', role='operator'
        )
        from django.utils import timezone
        self.call = Call.objects.create(
            operator=self.sultan,
            call_datetime=timezone.now(),
            status=Call.STATUS_NEW,
            external_call_id='CAtest002',
            from_phone='+77001234567',
        )

    def _post(self, call_id, attempt, dial_status):
        return self.client_api.post(
            _status_url(call_id, attempt),
            {'DialCallStatus': dial_status, 'CallSid': 'CAtest002'},
        )

    def test_completed_returns_empty_response(self):
        resp = self._post(self.call.pk, 0, 'completed')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'<Response>', resp.content)
        # Call status unchanged (recording callback will update it)
        self.call.refresh_from_db()
        self.assertEqual(self.call.status, Call.STATUS_NEW)

    def test_no_answer_tries_next_operator(self):
        resp = self._post(self.call.pk, 0, 'no-answer')
        self.assertEqual(resp.status_code, 200)
        # Should return TwiML dialling second operator
        self.assertIn(b'+996702110333', resp.content)

    def test_all_operators_exhausted_marks_failed(self):
        resp = self._post(self.call.pk, 1, 'no-answer')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'no operators are available', resp.content)
        self.call.refresh_from_db()
        self.assertEqual(self.call.status, Call.STATUS_FAILED)

    def test_unknown_call_id_returns_empty_response(self):
        resp = self._post(99999, 0, 'no-answer')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'<Response>', resp.content)


@override_settings(**TWILIO_SETTINGS)
class TwilioRecordingCallbackViewTest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.sultan = User.objects.create_user(
            username='Sultan', password='x', role='operator'
        )
        from django.utils import timezone
        self.call = Call.objects.create(
            operator=self.sultan,
            call_datetime=timezone.now(),
            status=Call.STATUS_NEW,
            external_call_id='CAtest003',
            from_phone='+77001234567',
        )

    def _fake_mp3(self):
        return b'ID3' + b'\x00' * 7 + b'\xff\xfb\x90\x00' + b'\x00' * 100

    @patch('apps.telephony_twilio.views.http_requests.get')
    def test_downloads_recording_and_triggers_analysis(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.content = self._fake_mp3()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        resp = self.client_api.post(
            _recording_url(),
            {
                'CallSid': 'CAtest003',
                'RecordingSid': 'REtest001',
                'RecordingStatus': 'completed',
            },
        )
        self.assertEqual(resp.status_code, 204)

        self.call.refresh_from_db()
        self.assertEqual(self.call.external_recording_id, 'REtest001')
        # Task runs eagerly in tests so status may advance to 'done'
        self.assertIn(self.call.status, (Call.STATUS_UPLOADED, Call.STATUS_DONE))
        self.assertTrue(CallRecording.objects.filter(call=self.call).exists())

    @patch('apps.telephony_twilio.views.http_requests.get')
    def test_uses_client_language_hint(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.content = self._fake_mp3()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # Give the call a client with kk language
        from django.utils import timezone
        client = Client.objects.create(primary_phone='+77001234567', language_hint='kk')
        self.call.client = client
        self.call.save(update_fields=['client'])

        with patch('apps.telephony_twilio.views.analyze_call_task') as mock_task:
            mock_task.delay = MagicMock()
            self.client_api.post(
                _recording_url(),
                {
                    'CallSid': 'CAtest003',
                    'RecordingSid': 'REtest002',
                    'RecordingStatus': 'completed',
                },
            )
            mock_task.delay.assert_called_once()
            _, kwargs = mock_task.delay.call_args
            self.assertEqual(kwargs.get('language_hint'), 'kk')

    def test_non_completed_recording_status_ignored(self):
        resp = self.client_api.post(
            _recording_url(),
            {
                'CallSid': 'CAtest003',
                'RecordingSid': 'REtest003',
                'RecordingStatus': 'in-progress',
            },
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(CallRecording.objects.filter(call=self.call).exists())

    @patch('apps.telephony_twilio.views.http_requests.get')
    def test_normalises_kz_language_hint(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.content = self._fake_mp3()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        # language_hint 'kk' should be passed through unchanged to the task
        from django.utils import timezone
        client = Client.objects.create(primary_phone='+77009999999', language_hint='kk')
        call2 = Call.objects.create(
            operator=self.sultan,
            call_datetime=timezone.now(),
            status=Call.STATUS_NEW,
            external_call_id='CAtest004',
            client=client,
        )

        with patch('apps.telephony_twilio.views.analyze_call_task') as mock_task:
            mock_task.delay = MagicMock()
            self.client_api.post(
                _recording_url(),
                {
                    'CallSid': 'CAtest004',
                    'RecordingSid': 'REtest004',
                    'RecordingStatus': 'completed',
                },
            )
            _, kwargs = mock_task.delay.call_args
            self.assertEqual(kwargs.get('language_hint'), 'kk')
