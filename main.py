import os
import sys
import asyncio
import logging
from aiohttp import web, ClientSession

# إجبار إخراج التيرمنال فوراً بدون تخزين مؤقت
sys.stdout.reconfigure(line_buffering=True)
print(">>> main.py script starting...", flush=True)

from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from config import bot, dp, ADMIN_ID
from database import init_db, close_db
from handlers import start, downloader, admin
from middlewares.throttling import AntiSpamMiddleware
import shutil
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def setup_bot_commands():
    user_commands = [
        BotCommand(command="start", description="🚀 Start Bot"),
        BotCommand(command="lang", description="🌐 Change Language"),
        BotCommand(command="help", description="📋 Supported Platforms"),
    ]
    try:
        await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    except Exception as e:
        print(f"⚠️ User command setup warning: {e}", flush=True)

async def health_check(request):
    return web.Response(text="Bot is running live on Render! 🚀")

async def self_ping_loop():
    """دالة التنشيط التلقائية لإبقاء البوت صاحي 24/7 على Render"""
    await asyncio.sleep(15) # انتظار إقلاع السيرفر
    
    # Render يمرر رابط المشروع تلقائياً في RENDER_EXTERNAL_URL
    raw_url = os.environ.get("RENDER_EXTERNAL_URL") or f"http://127.0.0.1:{os.environ.get('PORT', 8080)}"
    ping_url = raw_url if raw_url.startswith("http") else f"https://{raw_url}"
    
    print(f"[LOG] Self-Ping Service Active for: {ping_url}", flush=True)
    
    while True:
        try:
            async with ClientSession() as session:
                async with session.get(ping_url, timeout=10) as resp:
                    if resp.status == 200:
                        print("⚡ Keep-Alive Self-Ping Success! (Render Awake)", flush=True)
        except Exception as e:
            print(f"⚠️ Self-Ping Warning: {e}", flush=True)
        
        # إرسال ريكوست كل 4 دقائق (240 ثانية) لإيقاف مؤشر النوم الخاص بـ Render
        await asyncio.sleep(240)

async def main():
    print("==========================================", flush=True)
    print("🚀 STARTING BOT PROCESS ON RENDER", flush=True)
    print("==========================================", flush=True)

    # 1. تشغيل سيرفر الويب فوراً لربط المنفذ بـ Render
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web Server started successfully on port {port}", flush=True)

    # 2. تشغيل مهمة التنشيط الذاتي لمنع النوم تلقائياً
    asyncio.create_task(self_ping_loop())

    # 3. تنظيف مجلد التحميلات
    if os.path.exists("downloads"):
        try: shutil.rmtree("downloads")
        except Exception: pass
    os.makedirs("downloads", exist_ok=True)

    async def periodic_cleanup_task():
        """مهمة تنظيف دورية للملفات العالقة في مجلد التحميلات كل 10 دقائق"""
        while True:
            await asyncio.sleep(600)
            try:
                if os.path.exists("downloads"):
                    now = time.time()
                    for fname in os.listdir("downloads"):
                        fpath = os.path.join("downloads", fname)
                        if os.path.isfile(fpath) and (now - os.path.getmtime(fpath) > 600):
                            try: os.remove(fpath)
                            except Exception: pass
            except Exception:
                pass

    asyncio.create_task(periodic_cleanup_task())

    # 4. الاتصال بقاعدة البيانات
    await init_db()

    # 5. تفعيل Anti-Spam والراوترات
    dp.message.middleware(AntiSpamMiddleware(limit=4))
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(downloader.router)

    # 6. إعداد الأوامر
    await setup_bot_commands()

    try:
        bot_info = await bot.get_me()
        print(f"✅ Telegram Bot Connected: @{bot_info.username}", flush=True)
    except Exception as e:
        print(f"⚠️ Telegram Connection Warning: {e}", flush=True)

    print("⚡ Starting Polling Now...", flush=True)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        print(f"❌ Polling Fatal Error: {e}", flush=True)
    finally:
        await close_db()
        await bot.session.close()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot Stopped.", flush=True)