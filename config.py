import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID_RAW = os.getenv("ADMIN_ID") or "0"
ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW.isdigit() else 0
DATABASE_URL = os.getenv("DATABASE_URL")

COBALT_API_URL = os.getenv("COBALT_API_URL") or "https://api.cobalt.tools"
YOUTUBE_PROXY = os.getenv("YOUTUBE_PROXY") or None
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not BOT_TOKEN:
    print("[ERROR] BOT_TOKEN missing!", flush=True)
if not DATABASE_URL:
    print("[ERROR] DATABASE_URL missing!", flush=True)

storage = MemoryStorage()
session = AiohttpSession(timeout=600)

bot = Bot(
    token=BOT_TOKEN or "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ",
    session=session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=storage)

pyro_bot = None

SUPPORTED_LANGUAGES = {
    'ar': '🇦🇪 العربية',
    'en': '🇺🇸 English',
    'zh': '🇨🇳 中文',
    'fr': '🇫🇷 Français',
    'es': '🇪🇸 Español',
}