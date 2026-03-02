import io
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.calls.models import Call, Client, CallRecording, CallAnalysis, ScriptTemplate, ScriptStep


def create_default_script():
    template = ScriptTemplate.objects.create(
        name='Test Script RU',
        version='v1',
        is_default=True,
        language='ru',
    )
    ScriptStep.objects.create(
        template=template, order=1, key='greeting',
        keywords=['здравствуйте', 'добрый день'],
        required=True,
    )
    ScriptStep.objects.create(
        template=template, order=2, key='closing',
        keywords=['до свидания', 'всего хорошего'],
        required=True,
    )
    return template


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    MEDIA_ROOT='/tmp/test_media/',
)
class AnalyzeCallTestCase(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='operator2', password='testpass123', role='operator'
        )
        self.client_api.force_authenticate(user=self.user)

        self.crm_client = Client.objects.create(
            primary_phone='+77009876543',
            name='Analyze Client',
        )
        self.call = Call.objects.create(
            client=self.crm_client,
            operator=self.user,
            call_datetime=timezone.now(),
            status=Call.STATUS_NEW,
        )
        create_default_script()

    def _upload_recording(self):
        url = reverse('call-upload-recording', kwargs={'pk': self.call.pk})
        data = b'ID3' + b'\x00' * 7 + b'\xff\xfb\x90\x00' + b'\x00' * 100
        mp3 = io.BytesIO(data)
        mp3.name = 'call_audio.mp3'
        response = self.client_api.post(url, {'file': mp3}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_analyze_call(self):
        self._upload_recording()
        url = reverse('call-analyze', kwargs={'pk': self.call.pk})
        response = self.client_api.post(url, {'language_hint': 'ru'}, format='json')
        # With CELERY_TASK_ALWAYS_EAGER, task runs synchronously → 202 accepted
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_analyze_call_no_recording(self):
        url = reverse('call-analyze', kwargs={'pk': self.call.pk})
        response = self.client_api.post(url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_analysis(self):
        self._upload_recording()

        # Trigger analysis (eager)
        analyze_url = reverse('call-analyze', kwargs={'pk': self.call.pk})
        self.client_api.post(analyze_url, {'language_hint': 'ru'}, format='json')

        # Now GET analysis
        self.call.refresh_from_db()
        self.assertEqual(self.call.status, Call.STATUS_DONE)

        analysis_url = reverse('call-get-analysis', kwargs={'pk': self.call.pk})
        response = self.client_api.get(analysis_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertIn('transcript_text', data)
        self.assertIn('summary_short', data)
        self.assertIn('script_compliance', data)
        self.assertIn(str(self.call.id), data['transcript_text'])
