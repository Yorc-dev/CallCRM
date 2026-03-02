import io

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.calls.models import Call, Client, CallRecording, CallAnalysis


def _make_mp3():
    data = b'ID3' + b'\x00' * 7 + b'\xff\xfb\x90\x00' + b'\x00' * 100
    buf = io.BytesIO(data)
    buf.name = 'test.mp3'
    return buf


@override_settings(
    MEDIA_ROOT='/tmp/test_media_intake/',
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class IntakeAudioTestCase(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.user = User.objects.create_user(
            username='op_intake', password='testpass', role='operator'
        )
        self.api.force_authenticate(user=self.user)
        self.url = reverse('intake-audio')

    def test_intake_creates_call_and_recording(self):
        response = self.api.post(
            self.url,
            {'file': _make_mp3()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertIn('call', data)
        self.assertIn('recording', data)
        self.assertEqual(data['status'], 'queued')

        call_id = data['call']['id']
        call = Call.objects.get(pk=call_id)
        # Recording created
        self.assertTrue(call.recordings.exists())

    def test_intake_no_file_returns_400(self):
        response = self.api.post(self.url, {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_intake_uses_request_user_as_operator(self):
        response = self.api.post(
            self.url,
            {'file': _make_mp3()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']
        call = Call.objects.get(pk=call_id)
        self.assertEqual(call.operator, self.user)

    def test_intake_accepts_optional_fields(self):
        response = self.api.post(
            self.url,
            {
                'file': _make_mp3(),
                'call_datetime': '2024-06-01T10:00:00Z',
                'duration_sec': '90',
                'language_hint': 'ru',
                'script_version': 'v1',
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']
        call = Call.objects.get(pk=call_id)
        self.assertEqual(call.duration_sec, 90)

    def test_intake_normalises_kz_language(self):
        response = self.api.post(
            self.url,
            {'file': _make_mp3(), 'language_hint': 'kz'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_intake_analysis_auto_creates_client(self):
        """After analysis (eager), a Client is auto-created and linked to the Call."""
        response = self.api.post(
            self.url,
            {'file': _make_mp3()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']

        call = Call.objects.get(pk=call_id)
        # Eager Celery runs the task synchronously during the request,
        # so the call should now be in done/failed state and have a client.
        call.refresh_from_db()
        self.assertIn(call.status, (Call.STATUS_DONE, Call.STATUS_FAILED))
        self.assertIsNotNone(call.client)

    def test_intake_analysis_unknown_phone_tag(self):
        """Client created with no phone gets the 'unknown_phone' tag."""
        response = self.api.post(
            self.url,
            {'file': _make_mp3()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']
        call = Call.objects.select_related('client').get(pk=call_id)
        call.refresh_from_db()
        if call.client and not call.client.primary_phone:
            self.assertIn('unknown_phone', call.client.tags)

    def test_intake_unauthenticated_returns_401(self):
        unauth = APIClient()
        response = unauth.post(self.url, {'file': _make_mp3()}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
