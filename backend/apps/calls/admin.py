from django.contrib import admin
from .models import Call, Client, CallRecording, CallAnalysis, ScriptStep, ScriptTemplate

admin.site.register(Call)
admin.site.register(Client)
admin.site.register(CallRecording)             
admin.site.register(CallAnalysis)
admin.site.register(ScriptTemplate)
admin.site.register(ScriptStep)