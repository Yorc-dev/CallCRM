# Audio Monitor (ingest) — приём аудио для CallCRM

Серверная часть мониторинга аудио. **Десктопный рекордер вынесен в отдельный
проект** (`../../AudioRecorder/`), здесь остаётся только приёмник.

```
[Рекордер: отдельный проект]  ──.enc──▶  [ingest :8080]  ──WAV──▶  [CallCRM + Celery]
 ../AudioRecorder (gui.py)               FastAPI            транскрибация (faster-whisper
 Win/Mac/Linux                           расшифровка        + sherpa-onnx) → БД
```

| Часть | Где | Что делает |
|-------|-----|------------|
| **Рекордер** | отдельный проект `AudioRecorder/` | Десктопное приложение записи. Шифрует и шлёт в ingest. |
| **ingest-сервис** | `ingest/` | Регистрация устройств, логин, приём `.enc`, расшифровка, пересылка WAV в CallCRM. Docker. **Не транскрибирует.** |
| **Транскрибация + анализ** | внутри CallCRM (`backend/apps/analysis`) | Celery: WAV → текст (faster-whisper + sherpa-onnx) → локальный LLM-анализ → `TranscriptionRecord` / `Analysis` / `Incident`. |

---

## 1. Запуск серверной части (Docker, любая ОС)

Из корня репозитория:

```bash
docker compose up -d --build
```

Поднимутся: `postgres`, `redis`, `backend` (CallCRM API :8000), `celery`,
`frontend` (:3000) и `ingest` (:8080).

Проверка ingest: `curl http://localhost:8080/` → `{"status":"ok",...}`.

### Включение реальной транскрибации (тяжёлый шаг)

ML-зависимости и модели не нужны для работы плумбинга — без них запись всё
равно создаётся, а текст помечается как «модели не установлены». Чтобы включить
настоящий ASR:

```bash
# 1. пересобрать backend/celery с ML-зависимостями (faster-whisper, sherpa-onnx, onnxruntime)
docker compose build backend celery

# 2. скачать модели в volume models_data (~1.5 ГБ, один раз)
docker compose run --rm backend python manage.py download_models
```

GPU не требуется: по умолчанию CPU (`USE_CUDA=0`). Для NVIDIA — `USE_CUDA=1`
(на macOS GPU не поддерживается CTranslate2, всегда CPU).

### Настройка точности транскрибации (env у сервисов `backend`/`celery`)

| Переменная | По умолчанию | Что делает |
|------------|--------------|------------|
| `WHISPER_MODEL` | `medium` | Размер модели: `tiny`/`base`/`small`/`medium`/`large-v3`. Больше = точнее и медленнее. |
| `ASR_COMPUTE_TYPE` | `int8_float32` | Квантизация: `int8` (быстро) → `int8_float32` → `float32` (точнее). |
| `ASR_BEAM_SIZE` | `5` | Ширина beam-поиска. Больше = чуть точнее, медленнее. |
| `ASR_INITIAL_PROMPT` | про колл-центр | Контекст-подсказка модели (домен, пунктуация). |
| `ASR_HOTWORDS` | пусто | Термины через запятую (бренды, имена, продукты) — резко повышают их распознавание. |
| `ASR_VAD_MIN_SILENCE_MS` | `500` | Порог тишины для нарезки речи. |

Пайплайн уже включает word-level тайминги (точная диаризация по словам), отсев
галлюцинаций (`compression_ratio`/`log_prob`/`no_speech`) и temperature-fallback.
Для максимума точности: `WHISPER_MODEL=large-v3` + `ASR_COMPUTE_TYPE=float32`.

---

## 2. Запуск клиента записи (Win / Mac / Linux)

Системная зависимость PortAudio:
- **macOS:** `brew install portaudio`
- **Ubuntu/Debian:** `sudo apt install -y libportaudio2`
- **Windows:** ничего ставить не нужно (идёт в wheel).

Tkinter (GUI) обычно уже есть в Python; если нет:
- **macOS (Homebrew Python):** `brew install python-tk`
- **Ubuntu/Debian:** `sudo apt install -y python3-tk`
- **Windows:** входит в установщик Python.

Запуск десктопного приложения (окно с кнопками **Запустить / Остановить**):

```bash
# macOS / Linux
cd audio-monitor/client
./run.sh
```

```powershell
# Windows (PowerShell)
cd audio-monitor\client
.\run.ps1
```

Клиент сам создаст venv и поставит зависимости. В окне укажите сервер/логин/пароль
и нажмите **Запустить** — пойдёт запись сегментами и отправка в ingest, в журнале
видны события. **Остановить** — пауза.

Безоконный режим (для серверов/автозапуска): `HEADLESS=1 ./run.sh`.

### Запись только речи (VAD) и шумоподавление

В окне есть галочки **«Записывать только речь (VAD)»** и **«Шумоподавление»**
(обе включены по умолчанию):
- **VAD** — отправляются только фрагменты с речью; тишина и короткий фоновый
  шум не пишутся и не транскрибируются (поэтому пустых записей больше нет).
- **Шумоподавление** — каждый фрагмент чистится (спектральное вычитание)
  перед отправкой.

Тонкая настройка через env клиента:

| Переменная | По умолчанию | Что делает |
|------------|--------------|------------|
| `VAD_ENABLED` | `1` | Режим «только речь». |
| `DENOISE_ENABLED` | `1` | Шумоподавление. |
| `VAD_AGGRESSIVENESS` | `3` | 0–3, выше = строже отсев шума (3 рекомендуется). |
| `SILENCE_TIMEOUT_SEC` | `1.2` | Пауза, после которой фраза считается завершённой. |
| `PREBUFFER_SEC` | `0.5` | Захват за полсекунды до начала речи. |
| `MIN_SPEECH_SEC` | `0.8` | Короче — считается шумом и отбрасывается. |

VAD использует `webrtcvad`; если он не установится — автоматически включается
встроенный энергетический детектор (без доп. зависимостей).

---

## 3. Безопасность

- Аудио шифруется на клиенте: случайный AES-256 ключ (DEK) на каждый сегмент,
  DEK оборачивается RSA-OAEP-SHA256 публичным ключом сервера. Сервер хранит
  приватный ключ и расшифровывает.
- Токен авторизации — RSA-шифрованный `session:fingerprint:timestamp` с окном
  5 секунд (защита от replay).
- M2M между ingest и CallCRM — общий `INGEST_TOKEN` (заголовок `X-Ingest-Token`).
  **Смените `dev-ingest-token-change-me` в продакшене.**
- Дефолтные пользователи ingest (`admin/adminpassword123`) задаются в
  `ingest/data/users.txt` — поменяйте.

---

## Учётные данные по умолчанию (демо)

| Что | Логин | Пароль |
|-----|-------|--------|
| Клиент → ingest | `admin` | `adminpassword123` |
| Клиент → ingest | `agent` | `agentpassword123` |
