"""
Unit tests for OpenAIAnalyzer that mock all OpenAI SDK calls.
"""
import io
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.calls.models import Call, Client, CallRecording, CallAnalysis, ScriptTemplate, ScriptStep
from apps.calls.analyzer_openai import OpenAIAnalyzer


def _create_script_template(language='ru'):
    template = ScriptTemplate.objects.create(
        name=f'Test Script {language.upper()}',
        version='v1',
        is_default=True,
        language=language,
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


def _make_call(operator, crm_client=None):
    return Call.objects.create(
        client=crm_client,
        operator=operator,
        call_datetime=timezone.now(),
        status=Call.STATUS_NEW,
    )


def _make_recording(call):
    """Create a minimal CallRecording with an in-memory file."""
    from django.core.files.base import ContentFile
    recording = CallRecording(
        call=call,
        mime_type='audio/mpeg',
        size_bytes=128,
        sha256='a' * 64,
    )
    recording.file.save('test_audio.mp3', ContentFile(b'ID3' + b'\x00' * 125), save=True)
    return recording


FAKE_INSIGHTS_RESPONSE = {
    'summary_short': 'Client called about billing.',
    'summary_structured': {
        'category': 'billing',
        'key_phrases': ['invoice', 'payment'],
        'topic': 'Billing issue',
    },
    'category': 'billing',
    'operator_coaching': {
        'advice': ['Greet the client properly.'],
        'score': 72,
    },
    'client_draft': {
        'name': 'Иван Петров',
        'phone': '+77001234567',
        'language': 'ru',
        'notes': 'Billing inquiry',
    },
}


def _mock_openai_client(transcript_text='Здравствуйте. До свидания.', insights=None):
    """Build a mock openai.OpenAI() instance."""
    if insights is None:
        insights = FAKE_INSIGHTS_RESPONSE

    import json

    mock_client = MagicMock()

    # Mock transcription: audio.transcriptions.create returns plain text
    mock_client.audio.transcriptions.create.return_value = transcript_text

    # Mock chat completion
    message = MagicMock()
    message.content = json.dumps(insights)
    choice = MagicMock()
    choice.message = message
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    chat_response = MagicMock()
    chat_response.choices = [choice]
    chat_response.usage = usage
    mock_client.chat.completions.create.return_value = chat_response

    return mock_client


@override_settings(
    OPENAI_API_KEY='test-key',
    OPENAI_TRANSCRIBE_MODEL='whisper-1',
    OPENAI_CHAT_MODEL='gpt-4o-mini',
    OPENAI_TIMEOUT_SEC=30,
    MEDIA_ROOT='/tmp/test_media_openai/',
)
class OpenAIAnalyzerTest(TestCase):

    def setUp(self):
        self.operator = User.objects.create_user(
            username='op_openai', password='pass', role='operator'
        )
        self.crm_client = Client.objects.create(
            primary_phone='+77009999999',
            name='Test Client',
        )
        self.call = _make_call(self.operator, self.crm_client)
        _create_script_template('ru')

    def _make_analyzer_with_mock(self, transcript='Здравствуйте. До свидания.', insights=None):
        mock_openai = _mock_openai_client(transcript, insights)
        analyzer = OpenAIAnalyzer()
        analyzer._get_client = lambda: mock_openai
        return analyzer, mock_openai

    def test_analyze_populates_transcript_text(self):
        recording = _make_recording(self.call)
        analyzer, _ = self._make_analyzer_with_mock()
        result = analyzer.analyze(self.call, language_hint='ru')
        self.assertEqual(result['transcript_text'], 'Здравствуйте. До свидания.')

    def test_analyze_populates_summary_short(self):
        recording = _make_recording(self.call)
        analyzer, _ = self._make_analyzer_with_mock()
        result = analyzer.analyze(self.call, language_hint='ru')
        self.assertEqual(result['summary_short'], 'Client called about billing.')

    def test_analyze_populates_category(self):
        recording = _make_recording(self.call)
        analyzer, _ = self._make_analyzer_with_mock()
        result = analyzer.analyze(self.call, language_hint='ru')
        self.assertEqual(result['category'], 'billing')

    def test_analyze_populates_script_score(self):
        """transcript with both greeting and closing keywords → score 1.0 (fraction)."""
        recording = _make_recording(self.call)
        transcript = 'Здравствуйте! Всего хорошего, до свидания.'
        analyzer, _ = self._make_analyzer_with_mock(transcript=transcript)
        result = analyzer.analyze(self.call, language_hint='ru')
        self.assertIn('script_score', result)
        self.assertIsInstance(result['script_score'], float)
        self.assertEqual(result['script_score'], 1.0)

    def test_script_score_zero_when_no_keywords(self):
        recording = _make_recording(self.call)
        transcript = 'Some unrelated text with no matching keywords.'
        analyzer, _ = self._make_analyzer_with_mock(transcript=transcript)
        result = analyzer.analyze(self.call, language_hint='ru')
        self.assertEqual(result['script_score'], 0.0)

    def test_language_hint_kz_normalized_to_kk(self):
        recording = _make_recording(self.call)
        analyzer, _ = self._make_analyzer_with_mock()
        result = analyzer.analyze(self.call, language_hint='kz')
        self.assertEqual(result['asr_language'], 'kk')

    def test_language_hint_kk_preserved(self):
        recording = _make_recording(self.call)
        analyzer, _ = self._make_analyzer_with_mock()
        result = analyzer.analyze(self.call, language_hint='kk')
        self.assertEqual(result['asr_language'], 'kk')

    def test_no_recording_raises_value_error(self):
        analyzer, _ = self._make_analyzer_with_mock()
        with self.assertRaises(ValueError):
            analyzer.analyze(self.call, language_hint='ru')

    def test_model_info_present(self):
        recording = _make_recording(self.call)
        analyzer, _ = self._make_analyzer_with_mock()
        result = analyzer.analyze(self.call, language_hint='ru')
        self.assertIn('model_info', result)
        self.assertEqual(result['model_info']['analyzer'], 'openai_v1')
        self.assertEqual(result['model_info']['transcribe_model'], 'whisper-1')

    def test_client_draft_phone_fallback_from_transcript(self):
        """If AI returns empty phone, regex extracts from transcript."""
        insights_no_phone = dict(FAKE_INSIGHTS_RESPONSE)
        insights_no_phone['client_draft'] = {
            'name': '', 'phone': '', 'language': 'ru', 'notes': ''
        }
        transcript = 'Говорит Иван Петров. Телефон: +77001234567.'
        recording = _make_recording(self.call)
        analyzer, _ = self._make_analyzer_with_mock(
            transcript=transcript, insights=insights_no_phone
        )
        result = analyzer.analyze(self.call, language_hint='ru')
        self.assertEqual(result['client_draft']['phone'], '+77001234567')


@override_settings(
    OPENAI_API_KEY='test-key',
    OPENAI_TRANSCRIBE_MODEL='whisper-1',
    OPENAI_CHAT_MODEL='gpt-4o-mini',
    OPENAI_TIMEOUT_SEC=30,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    MEDIA_ROOT='/tmp/test_media_openai/',
)
class OpenAIAnalyzerTaskTest(TestCase):

    def setUp(self):
        from rest_framework.test import APIClient
        from django.urls import reverse

        self.api_client = APIClient()
        self.operator = User.objects.create_user(
            username='op_task', password='pass', role='operator'
        )
        self.api_client.force_authenticate(user=self.operator)
        self.crm_client = Client.objects.create(primary_phone='+77000000001')
        self.call = _make_call(self.operator, self.crm_client)
        _create_script_template('ru')

    def _upload_recording(self):
        from django.urls import reverse
        url = reverse('call-upload-recording', kwargs={'pk': self.call.pk})
        data = b'ID3' + b'\x00' * 125
        mp3 = io.BytesIO(data)
        mp3.name = 'call_audio.mp3'
        response = self.api_client.post(url, {'file': mp3}, format='multipart')
        self.assertEqual(response.status_code, 201)

    def test_task_sets_status_done(self):
        """Full task integration: with mocked OpenAI, status transitions to done."""
        self._upload_recording()

        mock_openai = _mock_openai_client(
            transcript_text='Здравствуйте. До свидания.',
        )

        with patch('apps.calls.analyzer_openai.OpenAIAnalyzer._get_client', return_value=mock_openai):
            from django.urls import reverse
            url = reverse('call-analyze', kwargs={'pk': self.call.pk})
            response = self.api_client.post(url, {'language_hint': 'ru'}, format='json')

        self.assertEqual(response.status_code, 202)
        self.call.refresh_from_db()
        self.assertEqual(self.call.status, Call.STATUS_DONE)

    def test_task_populates_analysis_fields(self):
        self._upload_recording()

        mock_openai = _mock_openai_client(
            transcript_text='Здравствуйте. До свидания.',
        )

        with patch('apps.calls.analyzer_openai.OpenAIAnalyzer._get_client', return_value=mock_openai):
            from django.urls import reverse
            url = reverse('call-analyze', kwargs={'pk': self.call.pk})
            self.api_client.post(url, {'language_hint': 'ru'}, format='json')

        analysis = CallAnalysis.objects.get(call=self.call)
        self.assertIn('Здравствуйте', analysis.transcript_text)
        self.assertEqual(analysis.summary_short, 'Client called about billing.')
        self.assertIsNotNone(analysis.script_score)
        self.assertEqual(analysis.category, 'billing')
