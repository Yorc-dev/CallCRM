# CallCRM — Call Center CRM MVP

A minimalist, modern call center CRM built with Django REST Framework and React.

## Architecture

```
┌──────────────┐     HTTP/REST     ┌─────────────────┐
│   Frontend   │◄─────────────────►│     Backend     │
│  React/Vite  │                   │  Django + DRF   │
│  Port: 3000  │                   │  Port: 8000     │
└──────────────┘                   └────────┬────────┘
                                            │
                          ┌─────────────────┼─────────────────┐
                          │                 │                 │
                   ┌──────▼──────┐  ┌───────▼──────┐  ┌──────▼──────┐
                   │  PostgreSQL  │  │    Redis     │  │   Celery    │
                   │  (database) │  │   (broker)   │  │  (worker)   │
                   └─────────────┘  └──────────────┘  └─────────────┘
```

## Quick Start (Docker Compose)

### Prerequisites
- Docker & Docker Compose installed

### Steps

1. **Clone and start:**
   ```bash
   git clone https://github.com/Yorc-dev/CallCRM.git
   cd CallCRM
   docker-compose up --build
   ```

2. **Create admin user:**
   ```bash
   docker-compose exec backend python manage.py createsuperuser
   ```
   Or use the API:
   ```bash
   curl -X POST http://localhost:8000/api/auth/register/ \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin123","role":"admin"}'
   ```

3. **Access the app:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000/api/
   - Django Admin: http://localhost:8000/admin/

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up environment (optional, uses SQLite by default)
cp .env.example .env
# Edit .env as needed

python manage.py migrate
python manage.py loaddata fixtures/default_script.json
python manage.py createsuperuser
python manage.py runserver
```

**Run Celery worker** (for async analysis):
```bash
celery -A crm worker --loglevel=info
```

**Run tests:**
```bash
python manage.py test tests --verbosity=2
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env  # or create .env with VITE_API_URL=http://localhost:8000
npm run dev           # http://localhost:5173
```

## Environment Variables

### Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (dev key) | Django secret key — **change in production** |
| `DEBUG` | `1` | Debug mode |
| `DATABASE_URL` | SQLite | PostgreSQL connection string |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis broker URL |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hosts |
| `MEDIA_ROOT` | `./media` | Local path for uploaded files |
| `OPENAI_API_KEY` | _(empty)_ | OpenAI API key — enables real transcription & AI insights |
| `OPENAI_TRANSCRIBE_MODEL` | `whisper-1` | Whisper model for speech-to-text |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Chat model for structured insights |
| `OPENAI_TIMEOUT_SEC` | `120` | Request timeout in seconds for OpenAI API calls |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |

## User Roles

| Role | Permissions |
|------|-------------|
| `operator` | Read/write own calls; read clients tied to own calls |
| `chief` | Read all calls + analytics |
| `admin` | Full access including user and script management |

## Demo Workflow

### 1. Login
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
# Returns: {"access": "...", "refresh": "..."}

TOKEN="<access_token_from_above>"
```

### 2. Create a Client
```bash
curl -X POST http://localhost:8000/api/clients/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"primary_phone":"+7701234567","name":"John Doe","gender":"male","language_hint":"ru"}'
# Returns: {"id": 1, ...}
```

### 3. Create a Call
```bash
curl -X POST http://localhost:8000/api/calls/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"client":1,"call_datetime":"2024-01-15T10:00:00Z","duration_sec":120}'
# Returns: {"id": 1, "status": "new", ...}
```

### 4. Upload MP3 Recording
```bash
curl -X POST http://localhost:8000/api/calls/1/recording/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/call.mp3"
# Returns: {"id": 1, "sha256": "...", "size_bytes": 1234, ...}
# Call status → "uploaded"
```

### 5. Trigger Analysis
```bash
curl -X POST http://localhost:8000/api/calls/1/analyze/ \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"status": "queued", "call_id": 1}
# Call status → "processing" → "done"
```

### 6. View Analysis Results
```bash
curl http://localhost:8000/api/calls/1/analysis/ \
  -H "Authorization: Bearer $TOKEN"
# Returns full CallAnalysis including transcript, summary, script_compliance, coaching
```

### 7. Apply Client Draft
```bash
curl -X POST http://localhost:8000/api/calls/1/confirm-client/ \
  -H "Authorization: Bearer $TOKEN"
# Applies client_draft fields to the linked Client record
```

### 8. View Analytics (chief/admin)
```bash
curl "http://localhost:8000/api/analytics/overview?from=2024-01-01&to=2024-12-31" \
  -H "Authorization: Bearer $TOKEN"
# Returns total_calls, done_calls, failed_calls, avg_duration_sec, calls_per_day[]

curl "http://localhost:8000/api/analytics/operators?from=2024-01-01&to=2024-12-31" \
  -H "Authorization: Bearer $TOKEN"
# Returns per-operator call counts and avg duration
```

The React UI exposes an **Аналитика** page (`/analytics`) in the left sidebar, visible only to `chief` and `admin` roles. It shows a date-range filter (default: last 7 days), total/completed/failed call counts, a daily bar chart, and an operator statistics table.

## One-Shot Audio Intake (no pre-known client)

Upload an MP3 in a single request — no need to create a Client or Call first.
The system creates a Call + Recording immediately and queues background analysis,
which will automatically extract client details and link a Client record.

```bash
curl -X POST http://localhost:8000/api/intake/audio/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/call.mp3" \
  -F "language_hint=ru" \
  -F "call_datetime=2024-01-15T10:00:00Z" \
  -F "duration_sec=180"
# Returns:
# {
#   "call": { "id": 42, "status": "uploaded", ... },
#   "recording": { "id": 7, "sha256": "...", ... },
#   "analysis_queued": true
# }
```

### Fields

| Field | Required | Default | Notes |
|-------|----------|---------|-------|
| `file` | ✓ | — | MP3 audio file |
| `language_hint` | | `ru` | `ru`, `kk`, or `kz` (alias → `kk`) |
| `call_datetime` | | now | ISO-8601 datetime |
| `duration_sec` | | null | integer seconds |
| `script_version` | | `v1` | script template version |

After analysis completes (`status=done`), `GET /api/calls/{id}/analysis/` returns the
full transcript, summary, script compliance, and operator coaching.  The linked Client
record is accessible via `GET /api/calls/{id}/` → `client_detail`.

## API Reference

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/auth/login/` | Obtain JWT tokens | None |
| POST | `/api/auth/refresh/` | Refresh access token | None |
| POST | `/api/auth/register/` | Register user | None (DEBUG) / Admin |
| GET/POST | `/api/clients/` | List/create clients | All roles |
| GET/PUT/PATCH/DELETE | `/api/clients/{id}/` | Client CRUD | All roles |
| GET/POST | `/api/calls/` | List/create calls | All roles |
| GET/PUT/PATCH/DELETE | `/api/calls/{id}/` | Call CRUD | All roles |
| POST | `/api/calls/{id}/recording/` | Upload MP3 | All roles |
| POST | `/api/calls/{id}/analyze/` | Start analysis | All roles |
| GET | `/api/calls/{id}/analysis/` | Get analysis | All roles |
| POST | `/api/calls/{id}/confirm-client/` | Apply draft | All roles |
| POST | `/api/intake/audio/` | One-shot MP3 intake | All roles |
| GET | `/api/analytics/overview` | Overview stats + daily series | Chief/Admin |
| GET | `/api/analytics/operators` | Operator stats | Chief/Admin |
| GET | `/api/analytics/categories` | Category breakdown | Chief/Admin |

## Extending the System

### Swap ASR (Speech Recognition)
When `OPENAI_API_KEY` is set, the system automatically uses `OpenAIAnalyzer` (Whisper for transcription, GPT for insights). Without it, the keyword-based `PlaceholderAnalyzer` is used instead.
To use a different ASR provider, implement a class with the same `analyze(call, language_hint)` interface and wire it into `apps/calls/tasks.py`.

### Swap LLM (Summary/Coaching)
Edit `apps/calls/analyzer.py` → `PlaceholderAnalyzer.generate_summary()` and `generate_coaching()`. Replace with calls to OpenAI, Anthropic, or any LLM API.

### Add Script Templates
Use Django admin at `/admin/` or create fixtures. ScriptSteps define keyword lists for compliance checking.

### Webhooks / External CRM
The `ExternalIdentity` model provides the mapping table for external IDs. Add webhook dispatch in `apps/calls/tasks.py` after analysis completes.

## Default Script Template (v1, Russian)

| Step | Keywords |
|------|---------|
| greeting | здравствуйте, добрый день, добрый вечер, алло |
| name_ask | как вас зовут, представьтесь, ваше имя |
| need_identification | чем могу помочь, по какому вопросу, что случилось |
| solution_offer | предлагаю, могу предложить, рекомендую |
| confirmation | подтверждаете, согласны, верно, правильно |
| deadline | в течение, до конца, срок, когда |
| closing | спасибо за звонок, всего хорошего, до свидания |