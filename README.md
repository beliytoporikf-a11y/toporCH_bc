# toporCH Backend (Telegram Auth + Cloud Library)

Минимальный backend-шаблон для плеера:
- авторизация через Telegram Login payload;
- JWT-сессия для клиента;
- хранение библиотеки треков (метаданные) в БД.
- хранение аудиофайлов в облаке (Supabase Storage / Google Drive).

## Структура

- `backend/main.py` — вход FastAPI
- `backend/app/auth_telegram.py` — валидация Telegram payload (HMAC)
- `backend/app/routes_auth.py` — `/auth/telegram`, `/auth/me`
- `backend/app/routes_library.py` — CRUD-минимум для треков
- `backend/app/models.py` — SQLAlchemy модели
- `backend/app/database.py` — подключение к БД
- `backend/.env.example` — переменные окружения

## Быстрый запуск

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Для Render:
- в `Root Directory` укажи `backend`;
- `Build Command`: `pip install -r requirements.txt`;
- `Start Command`: `uvicorn main:app --host 0.0.0.0 --port $PORT`;
- Python фиксирован в `backend/runtime.txt` (`3.13.2`), чтобы избежать сборки `pydantic-core` через Rust.

Проверка:
- `GET http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`

## Telegram Auth

1. Создай бота через `@BotFather`.
2. В `.env` укажи `TELEGRAM_BOT_TOKEN`.
3. Для назначения админов укажи `TELEGRAM_ADMIN_IDS` (через запятую, Telegram user id).
4. Клиент передаёт payload Telegram Login на `POST /auth/telegram`.
5. Сервер проверяет hash и возвращает JWT.
6. Админ может назначать других админов: `POST /auth/admin/assign/{telegram_id}`.

Важно:
- вход по номеру/QR для Telegram-аккаунта через один `bot token` невозможен;
- для такого сценария нужен MTProto (`api_id` + `api_hash`) и отдельный flow.

## Google Drive (storage)

1. Создай service account в Google Cloud.
2. Включи Google Drive API.
3. Скачай JSON-ключ сервисного аккаунта.
4. Создай папку на Google Drive и поделись ей на email service account с правами Editor.
5. Заполни в `.env`:
   - `GOOGLE_DRIVE_ENABLED=true`
   - `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=путь_к_json`
   - `GOOGLE_DRIVE_FOLDER_ID=id_папки`

Эндпоинты:
- `POST /me/library/tracks/upload` — загрузка файла в Google Drive и запись в библиотеку.
- `GET /me/library/tracks/{track_id}/download` — скачивание файла из Google Drive.

## Supabase Storage (рекомендуется)

1. Создай bucket в Supabase Storage (например `music`).
2. В `.env` укажи:
   - `STORAGE_PROVIDER=supabase`
   - `SUPABASE_URL=https://<project-ref>.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY=<service_role_key>` (предпочтительно)
   - либо S3 credentials:
     - `SUPABASE_S3_ACCESS_KEY_ID`
     - `SUPABASE_S3_SECRET_ACCESS_KEY`
     - `SUPABASE_S3_REGION`
   - `SUPABASE_BUCKET=music`
3. Оставь bucket приватным (service role ключ даёт серверный доступ).

Эндпоинты те же:
- `POST /me/library/tracks/upload`
- `GET /me/library/tracks/{track_id}/download`

## Что дальше добавить

1. Объектное хранилище треков (S3/R2/MinIO) и `remote_file_key`.
2. Плейлисты и синхронизацию изменений `since`.
3. Refresh-token и отзыв токенов.
4. Rate-limit и аудит-логи.

## Keepalive (обход sleep/free downtime)

- Добавлен workflow: `.github/workflows/keepalive.yml`.
- Добавь в GitHub Secrets:
  - `KEEPALIVE_URL=https://<your-service>.onrender.com/health`
- Пинг будет идти каждые 10 минут.
