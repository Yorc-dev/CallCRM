from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.calls.models import Call, Client


class CallsFilterTestCase(TestCase):
    def setUp(self):
        self.client_api = APIClient()

        self.chief = User.objects.create_user(
            username='chief1', password='testpass123', role='chief'
        )
        self.operator1 = User.objects.create_user(
            username='operator_alice', first_name='Alice', last_name='Smith',
            password='testpass123', role='operator'
        )
        self.operator2 = User.objects.create_user(
            username='operator_bob', first_name='Bob', last_name='Jones',
            password='testpass123', role='operator'
        )

        self.crm_client1 = Client.objects.create(
            primary_phone='+77001111111', name='Ivanov Ivan'
        )
        self.crm_client2 = Client.objects.create(
            primary_phone='+77002222222', name='Petrov Petr'
        )

        self.call1 = Call.objects.create(
            client=self.crm_client1,
            operator=self.operator1,
            call_datetime=timezone.now(),
            status=Call.STATUS_NEW,
        )
        self.call2 = Call.objects.create(
            client=self.crm_client2,
            operator=self.operator2,
            call_datetime=timezone.now(),
            status=Call.STATUS_NEW,
        )

        self.url = reverse('call-list')

    def test_filter_by_client_name(self):
        self.client_api.force_authenticate(user=self.chief)
        response = self.client_api.get(self.url, {'client_name': 'Ivanov'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ids = [item['id'] for item in data]
        self.assertIn(self.call1.id, ids)
        self.assertNotIn(self.call2.id, ids)

    def test_filter_by_client_name_case_insensitive(self):
        self.client_api.force_authenticate(user=self.chief)
        response = self.client_api.get(self.url, {'client_name': 'ivanov'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ids = [item['id'] for item in data]
        self.assertIn(self.call1.id, ids)
        self.assertNotIn(self.call2.id, ids)

    def test_filter_by_operator_username(self):
        self.client_api.force_authenticate(user=self.chief)
        response = self.client_api.get(self.url, {'operator_name': 'alice'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ids = [item['id'] for item in data]
        self.assertIn(self.call1.id, ids)
        self.assertNotIn(self.call2.id, ids)

    def test_filter_by_operator_first_name(self):
        self.client_api.force_authenticate(user=self.chief)
        response = self.client_api.get(self.url, {'operator_name': 'Bob'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ids = [item['id'] for item in data]
        self.assertIn(self.call2.id, ids)
        self.assertNotIn(self.call1.id, ids)

    def test_no_filter_returns_all(self):
        self.client_api.force_authenticate(user=self.chief)
        response = self.client_api.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ids = [item['id'] for item in data]
        self.assertIn(self.call1.id, ids)
        self.assertIn(self.call2.id, ids)

    def test_operator_cannot_filter_other_operators_calls(self):
        """Operators only see their own calls; operator_name filter still applies but within own calls."""
        self.client_api.force_authenticate(user=self.operator1)
        response = self.client_api.get(self.url, {'operator_name': 'bob'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        # operator1 only sees own calls; bob's calls not visible
        self.assertEqual(len(data), 0)

    def test_filter_by_status(self):
        self.client_api.force_authenticate(user=self.chief)
        self.call1.status = Call.STATUS_DONE
        self.call1.save(update_fields=['status'])
        response = self.client_api.get(self.url, {'status': 'done'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ids = [item['id'] for item in data]
        self.assertIn(self.call1.id, ids)
        self.assertNotIn(self.call2.id, ids)

    def test_filter_by_date_range(self):
        import datetime
        self.client_api.force_authenticate(user=self.chief)
        # call1 has call_datetime=now; set call2 to a week ago
        self.call2.call_datetime = timezone.now() - datetime.timedelta(days=7)
        self.call2.save(update_fields=['call_datetime'])
        today = timezone.now().date().isoformat()
        response = self.client_api.get(self.url, {'from': today, 'to': today})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        ids = [item['id'] for item in data]
        self.assertIn(self.call1.id, ids)
        self.assertNotIn(self.call2.id, ids)
