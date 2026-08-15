from __future__ import annotations
import base64, hashlib, json, os
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken

BASE=Path(__file__).resolve().parent
DATA_DIR=BASE/"data"; KEY_FILE=DATA_DIR/"banner.key"; SETTINGS_FILE=DATA_DIR/"settings.enc"
DEFAULTS={"admin_password_hash":"","skolaonline_user":"","skolaonline_password":"","instagram_configured":False,"facebook_configured":False,"sync_token":"","uploaded_timetables":{},"timetable_last_sync":"","skolaonline_storage_state":None}

def _database_url(): return (os.environ.get("DATABASE_URL") or "").strip()
def _fernet():
    secret=os.environ.get("BANNER_ENCRYPTION_SECRET") or os.environ.get("SECRET_KEY")
    if secret:
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))
    DATA_DIR.mkdir(exist_ok=True)
    if not KEY_FILE.exists(): KEY_FILE.write_bytes(Fernet.generate_key())
    return Fernet(KEY_FILE.read_bytes().strip())
def _connect():
    import psycopg
    return psycopg.connect(_database_url())
def _init(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS banner_settings (id SMALLINT PRIMARY KEY CHECK(id=1), payload BYTEA NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())")
    conn.commit()
def load_settings():
    data=dict(DEFAULTS)
    if _database_url():
        try:
            with _connect() as conn:
                _init(conn)
                with conn.cursor() as cur:
                    cur.execute("SELECT payload FROM banner_settings WHERE id=1"); row=cur.fetchone()
            if not row: return data
            saved=json.loads(_fernet().decrypt(bytes(row[0])).decode())
            if isinstance(saved,dict): data.update(saved)
        except Exception as exc: print(f"[settings] PostgreSQL load failed: {exc}")
        return data
    if not SETTINGS_FILE.exists(): return data
    try:
        saved=json.loads(_fernet().decrypt(SETTINGS_FILE.read_bytes()).decode())
        if isinstance(saved,dict): data.update(saved)
    except Exception: pass
    return data
def save_settings(data):
    payload=dict(DEFAULTS); payload.update(data)
    encrypted=_fernet().encrypt(json.dumps(payload,ensure_ascii=False).encode())
    if _database_url():
        with _connect() as conn:
            _init(conn)
            with conn.cursor() as cur:
                cur.execute("INSERT INTO banner_settings(id,payload,updated_at) VALUES(1,%s,NOW()) ON CONFLICT(id) DO UPDATE SET payload=EXCLUDED.payload, updated_at=NOW()",(encrypted,))
            conn.commit()
        return
    DATA_DIR.mkdir(exist_ok=True); SETTINGS_FILE.write_bytes(encrypted)
