import hashlib

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView

from .models import Client, Call, CallRecording, CallAnalysis
from .serializers import (
    ClientSerializer, CallSerializer, CallRecordingSerializer, CallAnalysisSerializer
)
from .permissions import CallPermission, IsChiefOrAdmin
from .tasks import analyze_call as analyze_call_task


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]


class CallViewSet(viewsets.ModelViewSet):
    serializer_class = CallSerializer
    permission_classes = [permissions.IsAuthenticated, CallPermission]

    def get_queryset(self):
        user = self.request.user
        qs = Call.objects.select_related('client', 'operator').prefetch_related('recordings')
        if user.role in ('chief', 'admin'):
            qs = qs.all()
        else:
            qs = qs.filter(operator=user)

        client_name = self.request.query_params.get('client_name', '').strip()
        if client_name:
            qs = qs.filter(client__name__icontains=client_name)

        operator_name = self.request.query_params.get('operator_name', '').strip()
        if operator_name:
            qs = qs.filter(
                Q(operator__username__icontains=operator_name)
                | Q(operator__first_name__icontains=operator_name)
                | Q(operator__last_name__icontains=operator_name)
            )

        from_date = self.request.query_params.get('from', '').strip()
        if from_date:
            parsed = parse_date(from_date)
            if parsed:
                qs = qs.filter(call_datetime__date__gte=parsed)

        to_date = self.request.query_params.get('to', '').strip()
        if to_date:
            parsed = parse_date(to_date)
            if parsed:
                qs = qs.filter(call_datetime__date__lte=parsed)

        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    def perform_create(self, serializer):
        # If operator role, force operator=self; chiefs/admins can set any operator
        user = self.request.user
        if user.role == 'operator':
            serializer.save(operator=user)
        else:
            serializer.save()

    @action(detail=True, methods=['post'], url_path='recording',
            parser_classes=[MultiPartParser, FormParser])
    def upload_recording(self, request, pk=None):
        call = self.get_object()
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Compute sha256
        sha256 = hashlib.sha256()
        for chunk in file_obj.chunks():
            sha256.update(chunk)
        sha256_hex = sha256.hexdigest()
        file_obj.seek(0)

        mime_type = file_obj.content_type or 'audio/mpeg'
        size_bytes = file_obj.size

        recording = CallRecording.objects.create(
            call=call,
            file=file_obj,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256_hex,
        )

        update_fields = ['status']
        duration_sec = request.data.get('duration_sec')
        if duration_sec is not None:
            try:
                call.duration_sec = int(duration_sec)
                update_fields.append('duration_sec')
            except (ValueError, TypeError):
                pass

        call.status = Call.STATUS_UPLOADED
        call.save(update_fields=update_fields)

        serializer = CallRecordingSerializer(recording, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='analyze')
    def analyze(self, request, pk=None):
        call = self.get_object()

        if not call.recordings.exists():
            return Response(
                {'detail': 'Call has no recording. Upload a recording first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        language_hint = request.data.get('language_hint', 'ru')
        # Normalize kz -> kk
        if language_hint == 'kz':
            language_hint = 'kk'
        script_version = request.data.get('script_version', 'v1')

        analyze_call_task.delay(call.id, language_hint=language_hint, script_version=script_version)

        return Response(
            {'detail': 'Analysis task queued.', 'call_id': call.id},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['get'], url_path='analysis')
    def get_analysis(self, request, pk=None):
        call = self.get_object()
        analysis = get_object_or_404(CallAnalysis, call=call)
        serializer = CallAnalysisSerializer(analysis)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='confirm-client')
    def confirm_client(self, request, pk=None):
        call = self.get_object()
        analysis = get_object_or_404(CallAnalysis, call=call)
        draft = analysis.client_draft

        if not draft:
            return Response({'detail': 'No client draft available.'}, status=status.HTTP_400_BAD_REQUEST)

        if call.client:
            client = call.client
            if draft.get('name'):
                client.name = draft['name']
            if draft.get('language'):
                lang = draft['language']
                if lang == 'kz':
                    lang = 'kk'
                client.language_hint = lang
            if draft.get('gender') in ('male', 'female', 'unknown'):
                client.gender = draft['gender']
            if draft.get('notes'):
                tags = client.tags or []
                if draft['notes'] not in tags:
                    tags.append(draft['notes'])
                client.tags = tags
            client.save()
        else:
            phone = draft.get('phone', '').strip()
            lang = draft.get('language', 'ru')
            if lang == 'kz':
                lang = 'kk'
            gender = draft.get('gender', 'unknown')
            if phone:
                client, created = Client.objects.get_or_create(primary_phone=phone)
            else:
                created = True
                client = Client.objects.create(primary_phone='')
            if created:
                client.language_hint = lang
                client.tags = [draft['notes']] if draft.get('notes') else []
            if draft.get('name'):
                client.name = draft['name']
            if gender in ('male', 'female', 'unknown'):
                client.gender = gender
            client.save()
            call.client = client
            call.save(update_fields=['client'])

        return Response(ClientSerializer(client).data, status=status.HTTP_200_OK)


class AudioIntakeView(APIView):
    """
    POST /api/intake/audio/

    Accept an MP3 recording with no pre-known client info.  Creates a Call and
    CallRecording immediately, then enqueues background analysis which will
    auto-create/link a Client from the extracted draft fields.

    Fields (multipart/form-data):
      - file            (required)  MP3 audio
      - language_hint   (optional)  'ru' (default), 'kk', or 'kz' (alias for 'kk')
      - call_datetime   (optional)  ISO-8601 string; defaults to now
      - duration_sec    (optional)  integer
      - script_version  (optional)  default 'v1'
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        language_hint = request.data.get('language_hint', 'ru')
        if language_hint == 'kz':
            language_hint = 'kk'

        call_datetime_str = request.data.get('call_datetime', '')
        if call_datetime_str:
            call_datetime = parse_datetime(call_datetime_str)
            if call_datetime is None:
                return Response(
                    {'detail': 'Invalid call_datetime format. Use ISO-8601 (e.g. 2024-01-15T10:00:00Z).'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            call_datetime = timezone.now()

        duration_sec = request.data.get('duration_sec')
        if duration_sec is not None:
            try:
                duration_sec = int(duration_sec)
            except (ValueError, TypeError):
                duration_sec = None

        script_version = request.data.get('script_version', 'v1')

        # Create Call with status=uploaded
        call = Call.objects.create(
            operator=request.user,
            call_datetime=call_datetime,
            duration_sec=duration_sec,
            status=Call.STATUS_UPLOADED,
        )

        # Compute sha256 and create Recording
        sha256 = hashlib.sha256()
        for chunk in file_obj.chunks():
            sha256.update(chunk)
        sha256_hex = sha256.hexdigest()
        file_obj.seek(0)

        recording = CallRecording.objects.create(
            call=call,
            file=file_obj,
            mime_type=file_obj.content_type or 'audio/mpeg',
            size_bytes=file_obj.size,
            sha256=sha256_hex,
        )

        # Enqueue background analysis
        analyze_call_task.delay(call.id, language_hint=language_hint, script_version=script_version)

        return Response(
            {
                'call': CallSerializer(call, context={'request': request}).data,
                'recording': CallRecordingSerializer(recording, context={'request': request}).data,
                'analysis_queued': True,
            },
            status=status.HTTP_201_CREATED,
        )

