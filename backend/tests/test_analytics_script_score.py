from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.calls.models import Call, Client, CallAnalysis


class AnalyticsScriptScoreTestCase(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.chief = User.objects.create_user(
            username='chief_score', password='testpass123', role='chief'
        )
        self.operator = User.objects.create_user(
            username='operator_score', password='testpass123', role='operator'
        )
        self.client_api.force_authenticate(user=self.chief)

        crm_client = Client.objects.create(primary_phone='+77001234567')

        # done call with script_score=0.8
        self.done_call = Call.objects.create(
            client=crm_client,
            operator=self.operator,
            call_datetime=timezone.now(),
            status=Call.STATUS_DONE,
        )
        CallAnalysis.objects.create(
            call=self.done_call,
            script_score=0.8,
        )

        # done call with script_score=0.6
        self.done_call2 = Call.objects.create(
            client=crm_client,
            operator=self.operator,
            call_datetime=timezone.now(),
            status=Call.STATUS_DONE,
        )
        CallAnalysis.objects.create(
            call=self.done_call2,
            script_score=0.6,
        )

        # non-done call with script_score — should NOT affect avg
        self.failed_call = Call.objects.create(
            client=crm_client,
            operator=self.operator,
            call_datetime=timezone.now(),
            status=Call.STATUS_FAILED,
        )
        CallAnalysis.objects.create(
            call=self.failed_call,
            script_score=0.0,
        )

    def test_analysis_includes_script_score(self):
        url = reverse('call-get-analysis', kwargs={'pk': self.done_call.pk})
        response = self.client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('script_score', data)
        self.assertAlmostEqual(data['script_score'], 0.8)

    def test_overview_avg_script_score(self):
        url = reverse('analytics-overview')
        response = self.client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('avg_script_score', data)
        # avg of 0.8 and 0.6 = 0.7, rounded to percent = 70
        self.assertEqual(data['avg_script_score'], 70)

    def test_overview_avg_script_score_excludes_non_done(self):
        # Only done calls should count; failed call has score 0.0
        url = reverse('analytics-overview')
        response = self.client_api.get(url)
        data = response.json()
        # If failed call were included: avg(0.8, 0.6, 0.0) = 0.467 → 47
        # Correct (only done): avg(0.8, 0.6) = 0.7 → 70
        self.assertEqual(data['avg_script_score'], 70)

    def test_operators_avg_script_score(self):
        url = reverse('analytics-operators')
        response = self.client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(len(data) > 0)
        op_row = next(r for r in data if r['username'] == 'operator_score')
        self.assertIn('avg_script_score', op_row)
        self.assertEqual(op_row['avg_script_score'], 70)
