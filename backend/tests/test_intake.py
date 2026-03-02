import io

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.calls.models import Call, Client, CallRecording, CallAnalysis, ScriptTemplate, ScriptStep


def create_default_script():
    template = ScriptTemplate.objects.create(
        name='Intake Script RU',
        version='v1',
        is_default=True,
        language='ru',
    )
    ScriptStep.objects.create(
        template=template, order=1, key='greeting',
        keywords=['здравствуйте'],
        required=True,
    )
    return template


def _make_mp3():
    data = b'ID3' + b'\x00' * 7 + b'\xff\xfb\x90\x00' + b'\x00' * 100
    f = io.BytesIO(data)
    f.name = 'call.mp3'
    return f


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    MEDIA_ROOT='/tmp/test_media/',
)
class AudioIntakeTestCase(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='intake_operator', password='testpass123', role='operator'
        )
        self.client_api.force_authenticate(user=self.user)
        create_default_script()

    def _intake_url(self):
        return reverse('intake-audio')

    # ------------------------------------------------------------------
    # Basic creation tests
    # ------------------------------------------------------------------

    def test_creates_call_and_recording(self):
        """Uploading MP3 creates a Call (status=uploaded) and a CallRecording."""
        response = self.client_api.post(
            self._intake_url(),
            {'file': _make_mp3()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        # Response shape
        self.assertIn('call', data)
        self.assertIn('recording', data)
        self.assertTrue(data['analysis_queued'])

        call_id = data['call']['id']
        call = Call.objects.get(pk=call_id)

        # Status transitions: task runs eagerly so status ends at 'done'
        self.assertIn(call.status, (Call.STATUS_UPLOADED, Call.STATUS_DONE))

        # Recording exists
        self.assertTrue(CallRecording.objects.filter(call=call).exists())

    def test_no_file_returns_400(self):
        response = self.client_api.post(self._intake_url(), {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_returns_401(self):
        anon = APIClient()
        response = anon.post(self._intake_url(), {'file': _make_mp3()}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ------------------------------------------------------------------
    # Language hint normalisation
    # ------------------------------------------------------------------

    def test_language_kz_normalised_to_kk(self):
        """'kz' alias should be stored as 'kk' in the analysis."""
        response = self.client_api.post(
            self._intake_url(),
            {'file': _make_mp3(), 'language_hint': 'kz'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']
        # Task runs eagerly; analysis should exist
        analysis = CallAnalysis.objects.get(call_id=call_id)
        self.assertEqual(analysis.asr_language, 'kk')

    # ------------------------------------------------------------------
    # Optional fields
    # ------------------------------------------------------------------

    def test_optional_call_datetime_and_duration(self):
        response = self.client_api.post(
            self._intake_url(),
            {
                'file': _make_mp3(),
                'call_datetime': '2025-01-15T10:00:00Z',
                'duration_sec': '180',
                'script_version': 'v1',
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']
        call = Call.objects.get(pk=call_id)
        self.assertEqual(call.duration_sec, 180)

    # ------------------------------------------------------------------
    # Celery task: Client auto-creation
    # ------------------------------------------------------------------

    def test_task_creates_client_linked_to_call(self):
        """After eager task execution, a Client must be created and linked."""
        response = self.client_api.post(
            self._intake_url(),
            {'file': _make_mp3(), 'language_hint': 'ru'},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']

        call = Call.objects.select_related('client').get(pk=call_id)
        # Task ran eagerly, client should now be linked
        self.assertIsNotNone(call.client)
        self.assertIsInstance(call.client, Client)

    def test_task_extracts_phone_from_transcript(self):
        """Placeholder analyzer puts a fake phone in the transcript; task extracts it."""
        response = self.client_api.post(
            self._intake_url(),
            {'file': _make_mp3()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']

        call = Call.objects.select_related('client').get(pk=call_id)
        self.assertIsNotNone(call.client)
        # The placeholder transcript contains +77001234567
        self.assertNotEqual(call.client.primary_phone, '')

    def test_task_sets_status_done(self):
        response = self.client_api.post(
            self._intake_url(),
            {'file': _make_mp3()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']
        call = Call.objects.get(pk=call_id)
        self.assertEqual(call.status, Call.STATUS_DONE)

    # ------------------------------------------------------------------
    # Operator field
    # ------------------------------------------------------------------

    def test_operator_set_to_request_user(self):
        response = self.client_api.post(
            self._intake_url(),
            {'file': _make_mp3()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        call_id = response.json()['call']['id']
        call = Call.objects.get(pk=call_id)
        self.assertEqual(call.operator, self.user)
