from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.calls.models import Call, Client, CallAnalysis, ScriptTemplate, ScriptStep

FALLBACK_CRITERIA = [
    {'key': 'greeting', 'description': 'Приветствие'},
    {'key': 'name_ask', 'description': 'Уточнение имени'},
    {'key': 'confirmation', 'description': 'Подтверждение'},
    {'key': 'need_identification', 'description': 'Выявление потребности'},
    {'key': 'solution_offer', 'description': 'Предложение решения'},
    {'key': 'deadline', 'description': 'Согласование сроков'},
    {'key': 'closing', 'description': 'Завершение разговора'},
]


class AssistantCriteriaView(APIView):
    """GET /api/assistant/criteria/ — list operator scoring criteria."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        default_template = ScriptTemplate.objects.filter(is_default=True).first()
        if default_template:
            steps = ScriptStep.objects.filter(template=default_template).order_by('order')
            criteria = [
                {'key': s.key, 'description': s.description or s.key}
                for s in steps
            ]
            if criteria:
                return Response(criteria)
        return Response(FALLBACK_CRITERIA)


class AssistantQueryView(APIView):
    """POST /api/assistant/query/ — search across calls/clients and return answer."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        query = (request.data.get('query') or '').strip()
        if not query:
            return Response(
                {'detail': 'query is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answer, references = self._search(query, request.user)

        # Optionally enhance with LLM if OPENAI_API_KEY is available
        answer = self._maybe_enhance(query, answer, references)

        return Response({'answer': answer, 'references': references})

    # ------------------------------------------------------------------
    def _search(self, query, user):
        q = query.lower()
        references = []

        # Search clients
        client_qs = Client.objects.filter(
            Q(name__icontains=q) | Q(primary_phone__icontains=q)
        )[:5]
        for c in client_qs:
            references.append({
                'type': 'client',
                'id': c.id,
                'label': c.name or c.primary_phone,
                'detail': f'Phone: {c.primary_phone}',
            })

        # Search calls (restrict operators to their own calls)
        call_qs = Call.objects.select_related('client', 'operator')
        if user.role not in ('chief', 'admin'):
            call_qs = call_qs.filter(operator=user)

        call_qs = call_qs.filter(
            Q(category__icontains=q)
            | Q(client__name__icontains=q)
            | Q(client__primary_phone__icontains=q)
            | Q(from_phone__icontains=q)
            | Q(to_phone__icontains=q)
        )[:5]

        for call in call_qs:
            label = f'Call #{call.id}'
            if call.client:
                label += f' — {call.client.name or call.client.primary_phone}'
            references.append({
                'type': 'call',
                'id': call.id,
                'label': label,
                'detail': f'Status: {call.status}, Date: {call.call_datetime.date().isoformat() if call.call_datetime else ""}',
            })

        # Search analysis transcripts / summaries
        analysis_qs = CallAnalysis.objects.select_related('call').filter(
            Q(transcript_text__icontains=q) | Q(summary_short__icontains=q)
        )
        if user.role not in ('chief', 'admin'):
            analysis_qs = analysis_qs.filter(call__operator=user)
        analysis_qs = analysis_qs[:5]

        seen_call_ids = {r['id'] for r in references if r['type'] == 'call'}
        for a in analysis_qs:
            if a.call_id not in seen_call_ids:
                references.append({
                    'type': 'call',
                    'id': a.call_id,
                    'label': f'Call #{a.call_id} (transcript match)',
                    'detail': a.summary_short[:120] if a.summary_short else '',
                })
                seen_call_ids.add(a.call_id)

        total = len(references)
        if total == 0:
            answer = f'По запросу «{query}» ничего не найдено.'
        elif total == 1:
            answer = f'По запросу «{query}» найдено 1 совпадение.'
        elif 2 <= total <= 4:
            answer = f'По запросу «{query}» найдено {total} совпадения.'
        else:
            answer = f'По запросу «{query}» найдено {total} совпадений.'
        return answer, references

    def _maybe_enhance(self, query, answer, references):
        """Optionally use OpenAI to produce a better answer."""
        import os
        api_key = os.environ.get('OPENAI_API_KEY', '')
        if not api_key or not references:
            return answer
        try:
            import openai
            openai.api_key = api_key
            context = '\n'.join(
                f"- [{r['type']}#{r['id']}] {r['label']}: {r['detail']}"
                for r in references
            )
            prompt = (
                f"User query: {query}\n\n"
                f"Relevant CRM records:\n{context}\n\n"
                "Provide a concise helpful answer based on these records."
            )
            resp = openai.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{'role': 'user', 'content': prompt}],
                max_tokens=300,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return answer
