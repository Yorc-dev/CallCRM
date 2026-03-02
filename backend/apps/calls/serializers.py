from rest_framework import serializers
from .models import Client, Call, CallRecording, CallAnalysis, ScriptTemplate, ScriptStep, ExternalIdentity
from apps.accounts.serializers import UserPublicSerializer


def normalize_language(lang):
    """Normalize 'kz' -> 'kk' for language_hint."""
    if lang == 'kz':
        return 'kk'
    return lang


class ClientSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='name', required=False)
    phone = serializers.CharField(source='primary_phone', required=False)

    class Meta:
        model = Client
        fields = ('id', 'full_name', 'name', 'phone', 'primary_phone',
                  'gender', 'language_hint', 'tags', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_language_hint(self, value):
        return normalize_language(value)


class CallRecordingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallRecording
        fields = ('id', 'call', 'file', 'mime_type', 'size_bytes', 'sha256', 'uploaded_at')
        read_only_fields = ('id', 'call', 'uploaded_at')


class CallAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallAnalysis
        fields = '__all__'
        read_only_fields = ('id', 'call', 'created_at', 'updated_at')


class ScriptStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScriptStep
        fields = '__all__'


class ScriptTemplateSerializer(serializers.ModelSerializer):
    steps = ScriptStepSerializer(many=True, read_only=True)

    class Meta:
        model = ScriptTemplate
        fields = '__all__'


class CallRecordingDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallRecording
        fields = ('id', 'file', 'uploaded_at')


class CallSerializer(serializers.ModelSerializer):
    operator_detail = UserPublicSerializer(source='operator', read_only=True)
    client_detail = ClientSerializer(source='client', read_only=True)
    has_recording = serializers.SerializerMethodField()
    has_analysis = serializers.SerializerMethodField()
    recording = serializers.SerializerMethodField()
    # Frontend-friendly aliases
    started_at = serializers.DateTimeField(source='call_datetime', required=False)
    duration = serializers.IntegerField(source='duration_sec', required=False, allow_null=True)

    class Meta:
        model = Call
        fields = (
            'id', 'client', 'operator', 'operator_detail', 'client_detail',
            'call_datetime', 'started_at', 'duration_sec', 'duration',
            'status', 'category',
            'has_recording', 'has_analysis', 'recording', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'status', 'created_at', 'updated_at')

    def get_has_recording(self, obj):
        return obj.recordings.exists()

    def get_has_analysis(self, obj):
        return hasattr(obj, 'analysis')

    def get_recording(self, obj):
        recording = obj.recordings.order_by('-uploaded_at').first()
        if recording is None:
            return None
        return CallRecordingDetailSerializer(recording, context=self.context).data


class ExternalIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalIdentity
        fields = '__all__'
