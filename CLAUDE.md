# CLAUDE.md — контекст проекта для новой сессии

Этот файл — «передача дел». Прочитай его целиком, чтобы понять, что за система,
что уже сделано и что осталось. Язык общения с пользователем — **русский**.

---

## Что это за проект

Система мониторинга и анализа разговоров. Состоит из **двух отдельных проектов**:

1. **CallCRM** (эта папка, `~/Desktop/CallCRM`) — серверная часть на сервере:
   веб-CRM + приём записей + транскрибация + диаризация + анализ.
2. **AudioRecorder** (`~/Desktop/AudioRecorder`, **отдельный проект, не в этом
   git-репозитории**) — десктопное приложение записи, ставится на ПК сотрудника.
   Записывает микрофон, шифрует, шлёт в CallCRM.

Git-репозиторий CallCRM: `git@github.com:Yorc-dev/CallCRM.git`, рабочая ветка
`tima` (основная — `main`).

---

## Архитектура CallCRM (docker-compose, 7 сервисов)

| Сервис | Порт | Что делает |
|--------|------|-----------|
| frontend | 3000 | Веб-CRM (React + Vite + Tailwind) |
| backend | 8000 | Django REST API |
| celery | — | Фоновые задачи: транскрибация + анализ |
| ingest | 8080 | FastAPI: приём зашифрованных записей от рекордера → пересылка в CallCRM |
| ollama | 11434 | Локальный LLM для анализа (бесплатно, оффлайн) |
| postgres | 5432 | БД |
| redis | 6379 | Брокер Celery |

Поток: **Рекордер → ingest (расшифровка) → CallCRM `/api/analysis/ingest/`
→ Celery (транскрибация faster-whisper + диаризация sherpa-onnx) → LLM-анализ
(Ollama) → БД**.

### Django-приложения (`backend/apps/`)
- `accounts` — пользователи (роли operator/chief/admin), JWT.
- `staff` — Company, Employee, EmployeeGroup, Department(в analysis), Category,
  **TranscriptionRecord** (записи), **Analysis**, **Incident**. Привязка устройств
  (`device-bind`), ingest-эндпоинт. Скоупинг данных по компании (admin видит всё).
- `analysis` — движок: `engine/transcribe.py` (Whisper+sherpa),
  `engine/llm.py` (Ollama), `tasks.py` (Celery `transcribe_recording`,
  `analyze_recording`), `prompts.py` (динамический промптинг),
  модели Department, PromptList, AnalysisCriterion, CompanyAnalysisSettings.
- `billing` — Plan (тарифы per_user/fixed), overview «Главной АИС».
- `calls`, `analytics`, `telephony_twilio` — более ранний функционал звонков.

### Ключевые модели
- `TranscriptionRecord`: employee, audio, record_datetime, text, is_original,
  session_id, **transcript_segments** (JSON: [{start,end,speaker,text}]).
- `Incident`: record, analysis, **start_minutes/end_minutes** (тайминг),
  **description**, **severity** (low/medium/high).
- `Plan`: billing_type (per_user/fixed), rate, price, max_users, features.

---

## Как это работает (важные детали)

- **Сегменты vs Оригинал.** Рекордер пишет короткие VAD-сегменты (по репликам) +
  один «сплошной оригинал» всей сессии (`is_original=True`). И сегменты, И оригинал
  теперь **транскрибируются, диаризуются и анализируются**. Разделение спикеров
  «кто что говорил» лучше всего видно на оригинале (весь разговор).
- **Диаризация.** sherpa-onnx, порог `DIARIZE_THRESHOLD=0.42` (0.8 слепляло всех в
  одного — это был баг). Для гарантированных 2 спикеров: `DIARIZE_NUM_SPEAKERS=2`.
- **Денойз перед ASR ВЫКЛЮЧЕН** (`DENOISE_ASR=0`): Whisper устойчив к шуму, денойз
  срезал форманты → мутный текст.
- **Инциденты с таймингом.** LLM получает транскрипт с метками `[start-end]` и
  возвращает `start_sec/end_sec` по инцидентам → сохраняется в минутах. Угрозы/
  оскорбления → severity high. Фронт показывает время как `M:SS`.
- **Привязка устройства.** Рекордер шлёт: ключ компании (Company.api_key) + email +
  пароль сотрудника. CallCRM (`/api/staff/device-bind/`) проверяет и привязывает
  записи к конкретному сотруднику. Ключи обрезаются от пробелов (была проблема с
  двойной вставкой / пробелами).

### Профиль качество/скорость (env у backend+celery в docker-compose.yml)
- Транскрибация (КАЧЕСТВО): `WHISPER_MODEL=medium`, `ASR_COMPUTE_TYPE=int8_float32`,
  `ASR_BEAM_SIZE=5`, полные переборы температур. ~2 мин на запись на CPU.
- Анализ (СКОРОСТЬ): `OLLAMA_MODEL=qwen2.5:1.5b`, `OLLAMA_KEEP_ALIVE=30m` (тёплая
  модель). ~20–30с.
- Главный потолок — **CPU**. GPU (`USE_CUDA=1`) дал бы кратное ускорение.
- Все параметры — env, легко менять (см. docker-compose.yml сервис celery).

---

## Доступы и тестовые данные

- Веб-CRM: http://localhost:3000 — **admin / admin12345** (роль admin, видит всё).
  Ещё есть **chief / chief12345** (видит только свою компанию).
- Тестовая привязка рекордера (компания «Ромашка ООО»):
  - Сервер (ingest): `http://localhost:8080`
  - Ключ компании: `Управление → Компании → Ключи` (или у chief@callcrm.kz —
    `2c4d9f765cfab1dfdc212e87e57fd6ba2dc666cb4d1623c38806075ccf31154e`)
  - Email: `chief@callcrm.kz` · Пароль: `test12345`
- INGEST_TOKEN (M2M ingest↔backend): `dev-ingest-token-change-me` (сменить в проде).

---

## Запуск / остановка

```bash
# CRM (нужен запущенный Docker Desktop)
cd ~/Desktop/CallCRM && docker compose up -d
# модели один раз: 
docker compose run --rm backend python manage.py download_models
docker compose exec ollama ollama pull qwen2.5:1.5b
# остановить
docker compose stop

# Рекордер
open ~/Desktop/AudioRecorder/dist/AudioMonitor.app   # mac, готовый бинарник
# или из исходников: cd ~/Desktop/AudioRecorder && ./run.sh
```

Проверки: `docker compose ps`; тесты бэка `docker compose exec -T backend python
manage.py test` (на момент написания — 53 теста зелёные); фронт-typecheck
`cd frontend && node_modules/.bin/tsc -b`.

---

## Документация
- `README.md` — подробная установка CRM «для не-программиста».
- `DEPLOY.md` — серверное развёртывание.
- `audio-monitor/README.md` — про ingest-сервис.
- `~/Desktop/AudioRecorder/README.md` — подробная установка рекордера.

---

## Что НЕ доделано / на будущее
- **PR не создан до конца:** изменения закоммичены и запушены в ветку `tima`
  (последний коммит `c3ab687`), но `gh` CLI не установлен и нет токена GitHub —
  PR через API/`gh` создать не удалось. Нужно: поставить `gh` (`brew install gh`),
  `gh auth login`, затем `gh pr create --base main --head tima`. Либо создать PR
  вручную на github.com (compare main...tima).
- Качество summary у `qwen2.5:1.5b` среднее (иногда дословно цитирует). Для лучшего
  — `OLLAMA_MODEL=qwen2.5:3b` (но медленнее на CPU).
- «Платёжка» из заметок и ERP (2-й этап) — не реализованы (по согласованию — позже).
- На реальных русских голосах диаризация/распознавание чище, чем на тестовых
  синтетических (использовался macOS `say` с голосами Milena/Anna для тестов).

---

## Стиль работы (как ожидает пользователь)
- Отвечать **по-русски**, кратко, по делу.
- Сразу делать (реализовывать), а не только обсуждать; проверять изменения
  (тесты/typecheck/E2E через curl и docker), сообщать реальные результаты.
- Перед запуском часто просят «запусти всё» / «останови всё» — это про
  `docker compose up -d` / `stop` + открыть/закрыть `AudioMonitor.app`.
