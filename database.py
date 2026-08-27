import os
import ssl
import socket
import asyncio
import urllib.parse
import sqlite3
import asyncpg
from config import DATABASE_URL

pool = None
use_sqlite = False
sqlite_path = "bot_data.db"

def _init_sqlite():
    global use_sqlite
    use_sqlite = True
    try:
        with sqlite3.connect(sqlite_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    lang_code TEXT DEFAULT 'ar',
                    is_banned INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        print("[LOG] Database ready (Mode: Local SQLite Storage)", flush=True)
    except Exception as e:
        print(f"[LOG] SQLite Init Warning: {e}", flush=True)

async def init_db():
    global pool, use_sqlite
    
    if not DATABASE_URL or "postgres" not in DATABASE_URL:
        print("[LOG] No external DATABASE_URL provided. Initializing local database...", flush=True)
        _init_sqlite()
        return

    print("[LOG] Initializing DB Connection to Supabase / PostgreSQL...", flush=True)
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        # محاولة الاتصال بـ Supabase مع مهلة سريعة
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            ssl=ctx,
            statement_cache_size=0,
            command_timeout=8,
            timeout=8
        )
        
        # إنشاء جدول المستخدمين تلقائياً إذا لم يكن موجوداً
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    lang_code VARCHAR(10) DEFAULT 'ar',
                    is_banned BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
        print("[LOG] Connected to Supabase DB successfully!", flush=True)
        use_sqlite = False
    except Exception as e:
        # في حال عدم توفر Supabase أو حدوث خطأ شبكة على السيرفر (IPv6 / Paused DB)، ننتقل تلقائياً لـ SQLite بدون توقف
        print(f"[LOG] External DB unavailable. Seamlessly activating Local SQLite Storage...", flush=True)
        pool = None
        _init_sqlite()

async def close_db():
    global pool
    if pool:
        try:
            await pool.close()
        except Exception:
            pass

async def get_or_create_user(user_id: int):
    default_user = {'id': user_id, 'lang_code': 'ar', 'is_banned': False}
    
    if pool and not use_sqlite:
        try:
            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO UPDATE SET id = EXCLUDED.id RETURNING *",
                    user_id
                )
                return dict(user) if user else default_user
        except Exception:
            pass

    # وضع SQLite
    try:
        def _get_or_create():
            with sqlite3.connect(sqlite_path) as conn:
                conn.execute("INSERT OR IGNORE INTO users (id, lang_code) VALUES (?, 'ar')", (user_id,))
                conn.commit()
                cur = conn.cursor()
                cur.execute("SELECT id, lang_code, is_banned FROM users WHERE id = ?", (user_id,))
                row = cur.fetchone()
                if row:
                    return {'id': row[0], 'lang_code': row[1] or 'ar', 'is_banned': bool(row[2])}
            return default_user
        return await asyncio.to_thread(_get_or_create)
    except Exception:
        return default_user

async def set_user_language(user_id: int, lang_code: str):
    if pool and not use_sqlite:
        try:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE users SET lang_code = $1 WHERE id = $2", lang_code, user_id)
                return
        except Exception:
            pass

    # وضع SQLite
    try:
        def _set_lang():
            with sqlite3.connect(sqlite_path) as conn:
                conn.execute("UPDATE users SET lang_code = ? WHERE id = ?", (lang_code, user_id))
                conn.commit()
        await asyncio.to_thread(_set_lang)
    except Exception:
        pass

async def is_user_banned(user_id: int) -> bool:
    if pool and not use_sqlite:
        try:
            async with pool.acquire() as conn:
                val = await conn.fetchval("SELECT is_banned FROM users WHERE id = $1", user_id)
                return bool(val)
        except Exception:
            pass

    # وضع SQLite
    try:
        def _is_banned():
            with sqlite3.connect(sqlite_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT is_banned FROM users WHERE id = ?", (user_id,))
                row = cur.fetchone()
                return bool(row[0]) if row else False
        return await asyncio.to_thread(_is_banned)
    except Exception:
        return False

async def set_ban_status(user_id: int, banned: bool):
    if pool and not use_sqlite:
        try:
            async with pool.acquire() as conn:
                await conn.execute("UPDATE users SET is_banned = $1 WHERE id = $2", banned, user_id)
                return
        except Exception:
            pass

    # وضع SQLite
    try:
        def _set_ban():
            with sqlite3.connect(sqlite_path) as conn:
                conn.execute("UPDATE users SET is_banned = ? WHERE id = ?", (1 if banned else 0, user_id))
                conn.commit()
        await asyncio.to_thread(_set_ban)
    except Exception:
        pass

async def get_bot_stats():
    if pool and not use_sqlite:
        try:
            async with pool.acquire() as conn:
                total_users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
                banned_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned = TRUE") or 0
                lang_counts = await conn.fetch("SELECT lang_code, COUNT(*) AS count FROM users GROUP BY lang_code")
                return total_users, banned_users, lang_counts
        except Exception:
            pass

    # وضع SQLite
    try:
        def _stats():
            with sqlite3.connect(sqlite_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM users")
                total = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
                banned = cur.fetchone()[0] or 0
                cur.execute("SELECT lang_code, COUNT(*) FROM users GROUP BY lang_code")
                langs = cur.fetchall()
                return total, banned, [{'lang_code': l[0], 'count': l[1]} for l in langs]
        return await asyncio.to_thread(_stats)
    except Exception:
        return 0, 0, []

async def get_user_ids_by_language(lang_code: str = "all"):
    if pool and not use_sqlite:
        try:
            async with pool.acquire() as conn:
                if lang_code == "all" or not lang_code:
                    rows = await conn.fetch("SELECT id FROM users WHERE is_banned = FALSE")
                else:
                    rows = await conn.fetch("SELECT id FROM users WHERE is_banned = FALSE AND lang_code = $1", lang_code)
                return [row['id'] for row in rows]
        except Exception:
            pass

    # وضع SQLite
    try:
        def _get_ids():
            with sqlite3.connect(sqlite_path) as conn:
                cur = conn.cursor()
                if lang_code == "all" or not lang_code:
                    cur.execute("SELECT id FROM users WHERE is_banned = 0")
                else:
                    cur.execute("SELECT id FROM users WHERE is_banned = 0 AND lang_code = ?", (lang_code,))
                rows = cur.fetchall()
                return [r[0] for r in rows]
        return await asyncio.to_thread(_get_ids)
    except Exception:
        return []