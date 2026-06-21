"""Ingest-сервис: приём записей с устройств и передача в CallCRM на транскрибацию.

Отдельный сервис (НЕ транскрибирует сам). Кроссплатформенный (Docker).
Поток: клиент -> /register -> /login -> /upload(.enc) -> расшифровка ->
       WAV(16k mono) -> POST в CallCRM /api/analysis/ingest/.
"""
import datetime
import io
import json
import os
import secrets
import time
import uuid
import wave
from typing import List, Optional

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

from crypto import (
    get_or_generate_keys, load_private_key,
    decrypt_token_rsa, decrypt_enc_bytes,
)

app = FastAPI(title="Audio Monitor Ingest Service")

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
STORAGE_DIR = os.path.join(DATA_DIR, "storage")
os.makedirs(STORAGE_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.txt")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.json")
DEVICES_FILE = os.path.join(DATA_DIR, "devices.json")

# Куда отправлять расшифрованный звук на транскрибацию (внутрь CallCRM)
CALLCRM_BASE_URL = os.environ.get("CALLCRM_BASE_URL", "http://backend:8000").rstrip("/")
CALLCRM_INGEST_URL = os.environ.get(
    "CALLCRM_INGEST_URL", f"{CALLCRM_BASE_URL}/api/analysis/ingest/"
)
CALLCRM_BIND_URL = os.environ.get(
    "CALLCRM_BIND_URL", f"{CALLCRM_BASE_URL}/api/staff/device-bind/"
)
INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "dev-ingest-token-change-me")
# URL, который сообщаем клиенту для загрузок (виден ему снаружи Docker)
PUBLIC_UPLOAD_URL = os.environ.get("PUBLIC_UPLOAD_URL", "http://localhost:8080/api/v1/upload")
SAMPLE_RATE = int(os.environ.get("SAMPLE_RATE", "16000"))

PRIVATE_KEY_PEM, PUBLIC_KEY_PEM = get_or_generate_keys()
PRIVATE_KEY = load_private_key(PRIVATE_KEY_PEM)

if not os.path.exists(USERS_FILE):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        f.write("user_1:admin:adminpassword123\n")
        f.write("user_2:agent:agentpassword123\n")


# ----------------------------- file-based state ----------------------------- #
def _load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def load_users():
    users = {}
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                parts = line.split(":")
                if len(parts) >= 3:
                    users[parts[1]] = {"user_id": parts[0], "password": parts[2]}
    return users


def save_session(session_key, user_id, fingerprint, company_key="", email=""):
    sessions = _load_json(SESSIONS_FILE)
    sessions[session_key] = {
        "user_id": user_id, "fingerprint": fingerprint,
        "company_key": company_key, "email": email,
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    _save_json(SESSIONS_FILE, sessions)


# ----------------------------- auth dependency ------------------------------ #
def get_auth(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.split("Bearer ", 1)[1]
    try:
        decrypted = decrypt_token_rsa(PRIVATE_KEY, token)
        session_key, fingerprint, unix_ts_str = decrypted.split(":")
        if abs(int(time.time()) - int(unix_ts_str)) > 5:
            raise HTTPException(status_code=401, detail="Replay attack detected")
        sessions = _load_json(SESSIONS_FILE)
        sess = sessions.get(session_key)
        if not sess:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        if sess["fingerprint"] != fingerprint:
            raise HTTPException(status_code=401, detail="Device fingerprint mismatch")
        return sess["user_id"], fingerprint, session_key
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth failed: {e}")


# ------------------------------- schemas ------------------------------------ #
class SpeechTrigger(BaseModel):
    enabled: bool = True
    prebuffer_sec: int = 5
    silence_timeout_sec: int = 10


class SchedulePeriod(BaseModel):
    from_time: str
    to: str


class RegistrationRequest(BaseModel):
    fingerprint: str
    hostname: str
    os: str
    os_version: str
    app_version: str
    microphones: List[str]


class RegistrationResponse(BaseModel):
    device_id: str
    server_public_key: str
    upload_url: str
    sample_rate: int = SAMPLE_RATE
    segment_duration_sec: int = 300
    overlap_duration_sec: int = 10
    speech_trigger: SpeechTrigger
    schedule: List[SchedulePeriod]


class LoginRequest(BaseModel):
    fingerprint: str
    encrypted_credentials: str       # RSA("email:password")
    company_key: str = ""            # ключ компании из CRM


class LoginResponse(BaseModel):
    status: str
    session_key: Optional[str] = None
    message: Optional[str] = None


# ------------------------------- endpoints ---------------------------------- #
@app.get("/")
async def root():
    return {"status": "ok", "service": "audio-monitor-ingest"}


@app.post("/api/v1/register", response_model=RegistrationResponse)
async def register_device(req: RegistrationRequest):
    device_id = f"dev_{uuid.uuid4().hex[:8]}"
    devices = _load_json(DEVICES_FILE)
    devices[device_id] = {
        "info": req.dict(),
        "registered_at": datetime.datetime.utcnow().isoformat(),
    }
    _save_json(DEVICES_FILE, devices)
    return RegistrationResponse(
        device_id=device_id,
        server_public_key=PUBLIC_KEY_PEM,
        upload_url=PUBLIC_UPLOAD_URL,
        speech_trigger=SpeechTrigger(),
        schedule=[SchedulePeriod(from_time="00:00", to="23:59")],
    )


async def _crm_bind(company_key: str, email: str, password: str):
    """Проверить привязку в CRM: ключ компании + сотрудник."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(CALLCRM_BIND_URL, json={
            "company_key": company_key, "email": email, "password": password,
        })
        if resp.status_code == 200 and resp.json().get("ok"):
            return resp.json(), None
        try:
            detail = resp.json().get("detail", "Привязка отклонена")
        except Exception:
            detail = "Привязка отклонена"
        return None, detail


@app.post("/api/v1/client/login", response_model=LoginResponse)
async def client_login(req: LoginRequest):
    try:
        creds = decrypt_token_rsa(PRIVATE_KEY, req.encrypted_credentials)
        email, password = creds.split(":", 1)
        # Привязка к компании+сотруднику через CRM
        bind, err = await _crm_bind(req.company_key, email, password)
        if err:
            return LoginResponse(status="error", message=err)
        session_key = secrets.token_hex(32)
        save_session(session_key, str(bind["employee_id"]), req.fingerprint,
                     company_key=req.company_key, email=email)
        return LoginResponse(status="success", session_key=session_key)
    except Exception as e:
        return LoginResponse(status="error", message=f"Login error: {e}")


@app.post("/api/v1/client/logout")
async def client_logout(auth=Depends(get_auth)):
    _, _, session_key = auth
    sessions = _load_json(SESSIONS_FILE)
    sessions.pop(session_key, None)
    _save_json(SESSIONS_FILE, sessions)
    return {"status": "success"}


def _pcm_to_wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


async def _forward_to_callcrm(wav_bytes: bytes, device_id: str, filename: str,
                              session_id: str = "", is_original: bool = False,
                              company_key: str = "", email: str = ""):
    """Отправить WAV в CallCRM на транскрибацию (M2M, по shared-token).

    company_key + email — привязка записи к компании/сотруднику в CRM.
    """
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                CALLCRM_INGEST_URL,
                headers={"X-Ingest-Token": INGEST_TOKEN},
                data={"device_id": device_id,
                      "recorded_at": datetime.datetime.utcnow().isoformat(),
                      "session_id": session_id,
                      "is_original": "true" if is_original else "false",
                      "company_key": company_key,
                      "email": email},
                files={"audio": (filename, wav_bytes, "audio/wav")},
            )
            print(f"CallCRM ingest -> {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"Failed to forward to CallCRM: {e}")


@app.post("/api/v1/upload")
async def upload_audio(
    device_id: str = Form(...),
    file: UploadFile = File(...),
    session_id: str = Form(""),
    is_original: str = Form("false"),
    auth=Depends(get_auth),
):
    _, fingerprint, session_key = auth
    original_flag = str(is_original).lower() in ("1", "true", "yes")
    sess = _load_json(SESSIONS_FILE).get(session_key, {})
    company_key = sess.get("company_key", "")
    email = sess.get("email", "")
    devices = _load_json(DEVICES_FILE)
    if device_id not in devices:
        raise HTTPException(status_code=403, detail="Device not registered")
    if devices[device_id]["info"]["fingerprint"] != fingerprint:
        raise HTTPException(status_code=403, detail="Device/fingerprint mismatch")

    enc_bytes = await file.read()
    # Сохраняем зашифрованный оригинал (аудит) + расшифровываем для пересылки
    today = datetime.date.today().isoformat()
    dev_dir = os.path.join(STORAGE_DIR, device_id, today)
    os.makedirs(dev_dir, exist_ok=True)
    with open(os.path.join(dev_dir, file.filename), "wb") as f:
        f.write(enc_bytes)

    try:
        pcm = decrypt_enc_bytes(enc_bytes, PRIVATE_KEY)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Decryption failed: {e}")

    wav_bytes = _pcm_to_wav_bytes(pcm)
    wav_name = os.path.splitext(file.filename)[0] + ".wav"
    await _forward_to_callcrm(wav_bytes, device_id, wav_name,
                              session_id=session_id, is_original=original_flag,
                              company_key=company_key, email=email)
    return {"status": "success", "filename": file.filename, "forwarded": True,
            "is_original": original_flag}
