# Telephony Twilio

## Views

### Inbound Call View
```python
from django.http import HttpResponse
from twilio.twiml.voice_response import VoiceResponse


def inbound_call(request):
    response = VoiceResponse()
    response.dial(record='record-from-answer', action='/api/twilio/voice/recording')
    return HttpResponse(str(response), content_type='text/xml')
```

### Status Callback View
```python
from django.http import JsonResponse


def call_status(request):
    # Handle status updates from Twilio
    pass
```

### Recording Callback View
```python
import requests
from myapp.models import CallRecording


def recording_callback(request):
    # Handle recording callback
    pass
```

## URL Routing

Add to `backend/crm/urls.py`:
```python
from django.urls import path
from .views import inbound_call, call_status, recording_callback

urlpatterns = [
    path('api/twilio/voice/inbound/', inbound_call, name='inbound_call'),
    path('api/twilio/voice/status/', call_status, name='call_status'),
    path('api/twilio/voice/recording/', recording_callback, name='recording_callback'),
]
```

## Settings

Add to `settings.py`:
```python
TWILIO_ACCOUNT_SID = 'your_account_sid'
TWILIO_AUTH_TOKEN = 'your_auth_token'
TWILIO_OPERATOR_NUMBERS = ['+1234567890']  # Add operator numbers here
```

## Tests

Write tests in `tests.py` using mocking for Twilio callbacks.