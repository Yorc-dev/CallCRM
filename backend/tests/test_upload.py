import io
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.calls.models import Call, Client, CallRecording


@override_settings(MEDIA_ROOT='/tmp/test_media/')
class UploadRecordingTestCase(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='operator1', password='testpass123', role='operator'
        )
        self.client_api.force_authenticate(user=self.user)

        self.crm_client = Client.objects.create(
            primary_phone='+77001234567',
            name='Test Client',
        )
        self.call = Call.objects.create(
            client=self.crm_client,
            operator=self.user,
            call_datetime=timezone.now(),
            status=Call.STATUS_NEW,
        )

    def _make_mp3_file(self):
        """Return a minimal fake MP3 file bytes."""
        # ID3 header + minimal data
        data = b'ID3' + b'\x00' * 7 + b'\xff\xfb\x90\x00' + b'\x00' * 100
        return io.BytesIO(data)

    def test_upload_recording(self):
        url = reverse('call-upload-recording', kwargs={'pk': self.call.pk})
        mp3 = self._make_mp3_file()
        mp3.name = 'test_call.mp3'

        response = self.client_api.post(
            url,
            {'file': mp3},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CallRecording.objects.filter(call=self.call).exists())
        recording = CallRecording.objects.get(call=self.call)
        self.assertIsNotNone(recording.sha256)
        self.assertGreater(len(recording.sha256), 0)

        # Call status should be 'uploaded'
        self.call.refresh_from_db()
        self.assertEqual(self.call.status, Call.STATUS_UPLOADED)

    def test_upload_recording_no_file(self):
        url = reverse('call-upload-recording', kwargs={'pk': self.call.pk})
        response = self.client_api.post(url, {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_call_detail_includes_recording(self):
        """Call detail endpoint should include recording object when recording exists."""
        # Upload a recording first
        upload_url = reverse('call-upload-recording', kwargs={'pk': self.call.pk})
        mp3 = self._make_mp3_file()
        mp3.name = 'test_call.mp3'
        self.client_api.post(upload_url, {'file': mp3}, format='multipart')

        # Fetch call detail
        detail_url = reverse('call-detail', kwargs={'pk': self.call.pk})
        response = self.client_api.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['has_recording'])
        self.assertIsNotNone(response.data['recording'])
        self.assertIn('id', response.data['recording'])
        self.assertIn('file', response.data['recording'])
        self.assertIn('uploaded_at', response.data['recording'])

    def test_call_detail_recording_null_when_no_recording(self):
        """Call detail endpoint should include recording=null when no recording exists."""
        detail_url = reverse('call-detail', kwargs={'pk': self.call.pk})
        response = self.client_api.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['has_recording'])
        self.assertIsNone(response.data['recording'])

    def test_upload_recording_saves_duration(self):
        """Providing duration_sec when uploading should persist it on the call."""
        url = reverse('call-upload-recording', kwargs={'pk': self.call.pk})
        mp3 = self._make_mp3_file()
        mp3.name = 'test_call.mp3'

        response = self.client_api.post(
            url,
            {'file': mp3, 'duration_sec': '120'},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.call.refresh_from_db()
        self.assertEqual(self.call.duration_sec, 120)
