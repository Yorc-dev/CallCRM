from django.urls import path
from . import views

urlpatterns = [
    path('voice/inbound/', views.TwilioInboundCallView.as_view(), name='twilio-inbound'),
    path('voice/status/', views.TwilioDialStatusView.as_view(), name='twilio-dial-status'),
    path('voice/recording/', views.TwilioRecordingCallbackView.as_view(), name='twilio-recording'),
]
