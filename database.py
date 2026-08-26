import asyncpg
import ssl
from config import DATABASE_URL

pool = None

async def init_db():
    global pool
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL is not set!", flush=True)
        return

    print("[LOG] Initializing DB Connection to Supabase...", flush=True)
    
    # إعداد سياق SSL لتجنب تعليق Supabase
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            ssl=ctx,
            statement_cache_size=0,
            command_timeout=15,
            timeout=15
        )
        print("✅ Connected to Supabase DB successfully!", flush=True)

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
        print("✅ Database tables verified and ready!", flush=True)
    except Exception as e:
        print(f"⚠️ DB Connection Error: {e}", flush=True)

async def close_db():
    global pool
    if pool:
        try:
            await pool.close()
        except Exception:
            pass

async def get_or_create_user(user_id: int):
    default_user = {'id': user_id, 'lang_code': 'ar', 'is_banned': False}
    if not pool:
        return default_user
    try:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "INSERT INTO users (id) VALUES ($1) ON CONFLICT (id) DO UPDATE SET id = EXCLUDED.id RETURNING *",
                user_id
            )
            return dict(user) if user else default_user
    except Exception as e:
        print(f"⚠️ DB get_or_create_user error: {e}", flush=True)
        return default_user

async def set_user_language(user_id: int, lang_code: str):
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET lang_code = $1 WHERE id = $2", lang_code, user_id)
    except Exception as e:
        print(f"⚠️ DB set_user_language error: {e}", flush=True)

async def is_user_banned(user_id: int) -> bool:
    if not pool:
        return False
    try:
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT is_banned FROM users WHERE id = $1", user_id)
            return bool(val)
    except Exception as e:
        print(f"⚠️ DB is_user_banned error: {e}", flush=True)
        return False

async def set_ban_status(user_id: int, banned: bool):
    if not pool:
        return
    try:
        async with pool.acquire() as conn:
            await conn.execute("UPDATE users SET is_banned = $1 WHERE id = $2", banned, user_id)
    except Exception as e:
        print(f"⚠️ DB set_ban_status error: {e}", flush=True)

async def get_bot_stats():
    if not pool:
        return 0, 0, []
    try:
        async with pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            banned_users = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_banned = TRUE") or 0
            lang_counts = await conn.fetch("SELECT lang_code, COUNT(*) AS count FROM users GROUP BY lang_code")
            return total_users, banned_users, lang_counts
    except Exception as e:
        print(f"⚠️ DB get_bot_stats error: {e}", flush=True)
        return 0, 0, []

async def get_user_ids_by_language(lang_code: str = "all"):
    if not pool:
        return []
    try:
        async with pool.acquire() as conn:
            if lang_code == "all" or not lang_code:
                rows = await conn.fetch("SELECT id FROM users WHERE is_banned = FALSE")
            else:
                rows = await conn.fetch("SELECT id FROM users WHERE is_banned = FALSE AND lang_code = $1", lang_code)
            return [row['id'] for row in rows]
    except Exception as e:
        print(f"⚠️ DB get_user_ids_by_language error: {e}", flush=True)
        return []