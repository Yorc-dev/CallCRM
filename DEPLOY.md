# Установка CallCRM на сервер

CRM (backend + frontend + ingest + celery + postgres + redis + ollama) ставится
**одним стеком через Docker**. Десктоп-рекордер — отдельный проект, ставится на
ПК пользователей (см. проект `AudioRecorder`).

## 1. Требования к серверу
- Linux (Ubuntu 22.04+ рекомендуется), 4+ ядра, 8+ ГБ RAM, ~15 ГБ диска
  (модели Whisper + Ollama ~4 ГБ).
- **Docker** + **Docker Compose**:
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```

## 2. Получить код и настроить
```bash
git clone <repo-url> callcrm && cd callcrm
```

Перед запуском поменяйте секреты в `docker-compose.yml` (или вынесите в `.env`):
- `SECRET_KEY` — длинная случайная строка
- `INGEST_TOKEN` — общий секрет между ingest и backend (любая случайная строка)
- `ALLOWED_HOSTS` — домен/IP сервера
- (для прод) `DEBUG=0`

## 3. Запуск
```bash
docker compose up -d --build
```
Поднимутся все сервисы. Проверка: `docker compose ps`.

## 4. Модели анализа (один раз, ~4 ГБ)
```bash
# транскрибация (Whisper + диаризация)
docker compose run --rm backend python manage.py download_models
# локальный LLM-анализ (бесплатно)
docker compose exec ollama ollama pull qwen2.5:3b
```

## 5. Создать администратора и компанию
```bash
docker compose exec backend python manage.py createsuperuser
```
Затем войдите во фронтенд и создайте компанию и сотрудников:
- **Фронтенд:** `http://<сервер>:3000`
- **Управление → Компании** → создать компанию → вкладка **«Ключи»** → скопировать
  **API Key компании** (он понадобится для привязки рекордеров).
- **Управление → Сотрудники** → создать сотрудников (email + пароль).

## 6. Порты (открыть/проксировать)
| Порт | Сервис | Кому нужен |
|------|--------|-----------|
| 3000 | Фронтенд (веб-CRM) | пользователям CRM |
| 8000 | Backend API | фронтенду |
| 8080 | **Ingest** | **десктоп-рекордерам на ПК** |
| 11434 | Ollama | внутренний |

В проде поставьте reverse-proxy (nginx/Caddy) с HTTPS перед 3000/8000/8080.
Рекордеры на ПК должны видеть **порт 8080** (или его проксированный адрес).

## Обновление / остановка
```bash
git pull && docker compose up -d --build   # обновить
docker compose stop                         # остановить
docker compose down                         # остановить и удалить контейнеры
```
