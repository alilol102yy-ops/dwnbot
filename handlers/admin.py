import asyncio
import psutil
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from database import set_ban_status, get_bot_stats, get_user_ids_by_language
from config import ADMIN_ID, bot

router = Router()

# فلتر أمان صارم: لمالك البوت فقط
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)


@router.callback_query(F.data.startswith("ban_user:"))
async def ban_user_callback(callback: CallbackQuery):
    try:
        target_user_id = int(callback.data.split(":")[1])
        await set_ban_status(target_user_id, True)
        await callback.answer(f"✅ تم حظر المستخدم {target_user_id} بنجاح!", show_alert=True)
        
        ban_tag = '\n\n<b><tg-emoji emoji-id="5240241223632954241">🚫</tg-emoji> [تم حظر هذا المستخدم بنجاح]</b>'
        
        if callback.message:
            if callback.message.caption is not None:
                new_caption = (callback.message.caption or "") + ban_tag
                await callback.message.edit_caption(caption=new_caption, reply_markup=None)
            else:
                new_text = (callback.message.text or "") + ban_tag
                await callback.message.edit_text(text=new_text, reply_markup=None)
    except Exception as e:
        print(f"⚠️ Ban user callback error: {e}", flush=True)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """أمر إحصائيات البوت - لمالك البوت فقط"""
    total, banned, lang_rows = await get_bot_stats()
    
    lang_str = ""
    for row in lang_rows:
        code = row['lang_code'] or 'غير محدد'
        count = row['count']
        lang_str += f"  • {code}: <b>{count}</b>\n"

    stats_msg = (
        f"📊 <b>إحصائيات البوت الحالية:</b>\n\n"
        f"👥 <b>إجمالي المستخدمين:</b> <code>{total}</code>\n"
        f'<tg-emoji emoji-id="5240241223632954241">🚫</tg-emoji> <b>المستخدمين المحظورين:</b> <code>{banned}</code>\n\n'
        f'<tg-emoji emoji-id="5447410659077661506">🌐</tg-emoji> <b>توزيع اللغات النشطة:</b>\n{lang_str}'
    )
    await message.answer(stats_msg)


@router.message(Command("server"))
async def cmd_server_health(message: Message):
    """أمر فحص صحة واستخدام السيرفر الـ CPU / RAM / Disk - لمالك البوت فقط"""
    cpu_usage = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    ram_used_gb = ram.used / (1024 ** 3)
    ram_total_gb = ram.total / (1024 ** 3)

    disk_free_gb = disk.free / (1024 ** 3)
    disk_total_gb = disk.total / (1024 ** 3)

    server_msg = (
        f'<tg-emoji emoji-id="5341715473882955310">⚙️</tg-emoji> <b>حالة السيرفر المباشرة (Server Health):</b>\n\n'
        f"💻 <b>استهلاك المعالج (CPU):</b> <code>{cpu_usage}%</code>\n"
        f"🧠 <b>استهلاك الذاكرة (RAM):</b> <code>{ram.percent}%</code> (<b>{ram_used_gb:.2f} GB</b> / {ram_total_gb:.2f} GB)\n"
        f"💽 <b>المساحة المتبقية (Disk Free):</b> <code>{disk_free_gb:.2f} GB</code> / {disk_total_gb:.2f} GB (<b>{disk.percent}% مستهلك</b>)\n\n"
        f'<tg-emoji emoji-id="5206607081334906820">✅</tg-emoji> <i>السيرفر يعمل بكفاءة.</i>'
    )
    await message.answer(server_msg)


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    """أمر الإذاعة الموجهة حسب اللغة - لمالك البوت فقط"""
    raw_args = message.text.replace("/broadcast", "").strip()
    if not raw_args:
        await message.answer(
            '<tg-emoji emoji-id="5424818078833715060">📢</tg-emoji> <b>طريقة الإذاعة الموجهة حسب اللغة:</b>\n\n'
            "اكتب الأمر متبوعاً بكود اللغة (ar, en, zh, fr, es, all) ثم نص الرسالة.\n\n"
            "<b>أمثلة للاستخدام:</b>\n"
            "• للجميع: <code>/broadcast all النص هنا</code>\n"
            "• للعرب فقط: <code>/broadcast ar النص هنا</code>\n"
            "• للإنجليز فقط: <code>/broadcast en Text here</code>\n\n"
            "<i>ملاحظة: الرسالة تصل للمستخدم كما هي تماماً بدون أي ديباجة إضافية.</i>"
        )
        return

    parts = raw_args.split(" ", 1)
    first_word = parts[0].lower()
    
    valid_langs = ['ar', 'en', 'zh', 'fr', 'es', 'all']
    if first_word in valid_langs and len(parts) > 1:
        target_lang = first_word
        text_to_send = parts[1].strip()
    else:
        target_lang = "all"
        text_to_send = raw_args

    user_ids = await get_user_ids_by_language(target_lang)
    lang_label = "جميع اللغات" if target_lang == "all" else f"لغة ({target_lang})"
    
    status_msg = await message.answer(f'<tg-emoji emoji-id="5424818078833715060">📢</tg-emoji> <i>جاري بث الرسالة لـ {lang_label} ({len(user_ids)} مستخدم)...</i>')
    
    success = 0
    failed = 0
    
    for uid in user_ids:
        try:
            try:
                await bot.send_message(uid, text_to_send)
            except Exception:
                # إذا فشل إرسال الـ HTML Entities يتم الإرسال كنص عادي
                await bot.send_message(uid, text_to_send, parse_mode=None)
            success += 1
            await asyncio.sleep(0.04)
        except Exception:
            failed += 1
    
    await status_msg.edit_text(
        f'<tg-emoji emoji-id="5206607081334906820">✅</tg-emoji> <b>تم الانتهاء من بث الرسالة!</b>\n\n'
        f"• المستهدفين: <b>{lang_label}</b>\n"
        f"• أُرسلت بنجاح إلى: <b>{success}</b> مستخدم\n"
        f"• تعذر الإرسال لـ: <b>{failed}</b> مستخدم"
    )