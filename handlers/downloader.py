import os
import time
import uuid
import html
import asyncio
from aiogram import Router, F
from aiogram.enums import ChatAction
from aiogram.types import Message, CallbackQuery, FSInputFile, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, ReactionTypeEmoji
from aiogram.fsm.context import FSMContext
from database import get_or_create_user, is_user_banned
from services.downloader import get_direct_stream_url, download_local_compressed, get_youtube_playlist_items
from config import bot, ADMIN_ID, pyro_bot
from locales.translations import get_text
from keyboards.inline import get_main_menu_keyboard

router = Router()

CONFETTI_EFFECT_ID = "5046509860389126442"

async def add_reaction_fast(message: Message):
    try:
        await message.react([ReactionTypeEmoji(emoji="👀")])
    except Exception:
        pass

async def update_status_safe(status_msg: Message, text: str):
    try:
        await status_msg.edit_text(text)
    except Exception:
        pass

async def forward_general_message_to_admin(user_msg: Message):
    """إعادة توجيه رسائل واستفسارات المستخدمين غير الروابط إلى مالك البوت بأمان"""
    if not ADMIN_ID or ADMIN_ID == 0:
        return
    try:
        user = user_msg.from_user
        if not user or user.id == ADMIN_ID:
            return
        
        user_name = user.full_name
        user_id = user.id
        username = f"@{user.username}" if user.username else "No Username ⚠️"
        text = user_msg.text or user_msg.caption or "[Media / Non-text message]"

        admin_text = (
            f"💬 <b>رسالة جديدة من مستخدم:</b>\n\n"
            f"👤 <b>الاسم:</b> {user_name}\n"
            f"🏷️ <b>المعرف:</b> {username}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n\n"
            f"📝 <b>الرسالة:</b>\n<blockquote>{html.escape(text)}</blockquote>"
        )
        ban_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚫 حظر المستخدم / Ban", callback_data=f"ban_user:{user_id}")]
        ])
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=ban_keyboard)
    except Exception as e:
        print(f"⚠️ Forward to admin error: {e}", flush=True)

async def notify_admin_with_media(sent_msg: Message, user_msg: Message, url: str, is_sensitive: bool = False):
    if not ADMIN_ID or ADMIN_ID == 0 or not sent_msg:
        return
    try:
        user = user_msg.from_user
        if not user:
            return
        user_name = user.full_name
        user_id = user.id
        username = f"@{user.username}" if user.username else "No Username ⚠️"
        sens_tag = '\n🔞 <b>Content Rating:</b> Sensitive Content' if is_sensitive else ""

        admin_caption = (
            f'📥 <b>New Media Downloaded:</b>\n\n'
            f"👤 <b>Name:</b> {user_name}\n"
            f"🏷️ <b>Username:</b> {username}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🔗 <b>URL:</b> {url}{sens_tag}"
        )
        
        ban_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚫 Ban User", callback_data=f"ban_user:{user_id}")]
        ])

        if hasattr(sent_msg, 'video') and sent_msg.video:
            await bot.send_video(ADMIN_ID, video=sent_msg.video.file_id, caption=admin_caption, reply_markup=ban_keyboard, has_spoiler=is_sensitive, supports_streaming=True)
        elif hasattr(sent_msg, 'photo') and sent_msg.photo:
            file_id = sent_msg.photo[-1].file_id if isinstance(sent_msg.photo, list) else sent_msg.photo.file_id
            await bot.send_photo(ADMIN_ID, photo=file_id, caption=admin_caption, reply_markup=ban_keyboard, has_spoiler=is_sensitive)
        elif hasattr(sent_msg, 'audio') and sent_msg.audio:
            await bot.send_audio(ADMIN_ID, audio=sent_msg.audio.file_id, caption=admin_caption, reply_markup=ban_keyboard)
        else:
            await bot.send_message(ADMIN_ID, admin_caption, reply_markup=ban_keyboard)
    except Exception as e:
        print(f"[LOG] Admin notify error: {e}", flush=True)

async def progress_callback(current, total, status_msg: Message, start_time_list: list):
    now = time.time()
    if now - start_time_list[0] < 3 and current < total:
        return
    start_time_list[0] = now
    
    try:
        percent = current * 100 / total
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        bar = '█' * int(percent / 10) + '▒' * (10 - int(percent / 10))
        
        text = (
            f"📤 <b>جاري الرفع المباشر...</b>\n"
            f"📊 <code>[{bar}] {percent:.1f}%</code>\n"
            f"📦 <code>{current_mb:.1f} MB / {total_mb:.1f} MB</code>"
        )
        await status_msg.edit_text(text)
    except Exception:
        pass

async def upload_file_smart(message: Message, filepath: str, m_type: str, caption: str, is_sensitive: bool, status_msg: Message, title: str = None, performer: str = None):
    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
    
    # 0. رفع ألبوم صور إذا كان الملف عبارة عن قائمة صور محلية
    if isinstance(filepath, list):
        try:
            if len(filepath) == 1:
                sent_msg = await message.answer_photo(
                    photo=FSInputFile(filepath[0]),
                    caption=caption,
                    has_spoiler=is_sensitive
                )
            else:
                media_group = [
                    InputMediaPhoto(media=FSInputFile(f_path), caption=caption if i == 0 else "", has_spoiler=is_sensitive)
                    for i, f_path in enumerate(filepath[:10])
                ]
                sent_msgs = await message.answer_media_group(media=media_group)
                sent_msg = sent_msgs[0] if sent_msgs else None
            return sent_msg
        except Exception as e:
            print(f"[LOG] Local photo album upload error: {e}", flush=True)
            return None

    # 1. الرفع عبر Pyrogram للملفات الأكبر من 48MB إذا كان مفعلاً
    if pyro_bot and getattr(pyro_bot, 'is_connected', False) and file_size > 48 * 1024 * 1024:
        try:
            start_time = [time.time()]
            if m_type == "audio":
                sent_msg = await pyro_bot.send_audio(
                    chat_id=message.chat.id,
                    audio=filepath,
                    caption=caption,
                    title=title,
                    performer=performer,
                    progress=progress_callback,
                    progress_args=(status_msg, start_time)
                )
            else:
                sent_msg = await pyro_bot.send_video(
                    chat_id=message.chat.id,
                    video=filepath,
                    caption=caption,
                    has_spoiler=is_sensitive,
                    supports_streaming=True,
                    progress=progress_callback,
                    progress_args=(status_msg, start_time)
                )
            return sent_msg
        except Exception as e:
            print(f"[LOG] Pyrogram Upload Error: {e}", flush=True)

    # 2. الرفع العادي عبر Aiogram للملفات حتى 50MB
    try:
        media_file = FSInputFile(filepath)
        if m_type == "audio":
            sent_msg = await message.answer_audio(
                audio=media_file, 
                caption=caption,
                title=title,
                performer=performer
            )
        elif m_type == "photo":
            sent_msg = await message.answer_photo(
                photo=media_file,
                caption=caption,
                has_spoiler=is_sensitive
            )
        else:
            sent_msg = await message.answer_video(
                video=media_file, 
                caption=caption, 
                has_spoiler=is_sensitive,
                supports_streaming=True
            )
        return sent_msg
    except Exception as e:
        print(f"[LOG] Aiogram Upload Error (File size: {file_size / (1024*1024):.2f}MB): {e}", flush=True)
        return None

async def send_media_with_auto_fallback(message: Message, url: str, status_msg: Message, clean_caption: str, lang: str) -> str:
    sensitive_warnings = {
        'ar': '\n\n🔞 <b>تنبيه:</b> <i>تم وضع تمويه لاحتمالية احتواء المقطع على محتوى +18.</i>',
        'en': '\n\n🔞 <b>Notice:</b> <i>Blurred due to potential adult content.</i>',
        'zh': '\n\n🔞 <b>注意:</b> <i>由于可能包含成人内容，已模糊处理。</i>',
        'fr': '\n\n🔞 <b>Avis:</b> <i>Flouté en raison d\'un contenu potentiel pour adultes.</i>',
        'es': '\n\n🔞 <b>Aviso:</b> <i>Difuminado debido a posible contenido para adultos.</i>'
    }

    asyncio.create_task(update_status_safe(status_msg, get_text('status_step2', lang)))

    direct_media, media_type, is_sensitive, title, performer = await get_direct_stream_url(url)
    
    if direct_media == "NO_MEDIA":
        await update_status_safe(status_msg, get_text('no_media', lang))
        return "NO_MEDIA"

    final_caption = clean_caption + (sensitive_warnings.get(lang, sensitive_warnings['en']) if is_sensitive else "")

    # إذا كان الرابط المباشر يحتوي على ألبوم صور أو ميديا متعددة
    if direct_media and isinstance(direct_media, list):
        try:
            asyncio.create_task(update_status_safe(status_msg, get_text('status_step3', lang)))
            photos = direct_media[:10]
            if len(photos) == 1:
                sent_msg = await message.answer_photo(photo=photos[0], caption=final_caption, has_spoiler=is_sensitive)
            else:
                media_group = [
                    InputMediaPhoto(media=u, caption=final_caption if i == 0 else "", has_spoiler=is_sensitive)
                    for i, u in enumerate(photos)
                ]
                sent_msgs = await message.answer_media_group(media=media_group)
                sent_msg = sent_msgs[0] if sent_msgs else None
            
            if sent_msg:
                asyncio.create_task(notify_admin_with_media(sent_msg, message, url, is_sensitive))
                return "SUCCESS"
        except Exception as e:
            print(f"[LOG] Direct photo album send failed: {e}", flush=True)

    # إذا كان الرابط المباشر نصياً لرابط ملف فيديو أو صوت أو صورة
    if direct_media and isinstance(direct_media, str):
        try:
            asyncio.create_task(update_status_safe(status_msg, get_text('status_step3', lang)))
            sent_msg = None
            if media_type == "audio":
                sent_msg = await message.answer_audio(audio=direct_media, caption=final_caption, title=title, performer=performer)
            elif media_type == "photo":
                sent_msg = await message.answer_photo(photo=direct_media, caption=final_caption, has_spoiler=is_sensitive)
            else:
                sent_msg = await message.answer_video(video=direct_media, caption=final_caption, has_spoiler=is_sensitive, supports_streaming=True)
            
            if sent_msg:
                asyncio.create_task(notify_admin_with_media(sent_msg, message, url, is_sensitive))
                return "SUCCESS"
        except Exception as e:
            print(f"[LOG] Direct send failed: {e}", flush=True)

    filepath = None
    try:
        asyncio.create_task(update_status_safe(status_msg, get_text('status_step2', lang)))

        info, filepath, m_type, is_sensitive, title, performer = await download_local_compressed(url)
        final_caption = clean_caption + (sensitive_warnings.get(lang, sensitive_warnings['en']) if is_sensitive else "")

        if filepath and os.path.exists(filepath):
            asyncio.create_task(update_status_safe(status_msg, get_text('status_step3', lang)))

            sent_msg = await upload_file_smart(
                message=message,
                filepath=filepath,
                m_type=m_type,
                caption=final_caption,
                is_sensitive=is_sensitive,
                status_msg=status_msg,
                title=title,
                performer=performer
            )

            if sent_msg:
                asyncio.create_task(notify_admin_with_media(sent_msg, message, url, is_sensitive))
                return "SUCCESS"
            else:
                print(f"[LOG] Upload returned None (File too large for Telegram 50MB limit)", flush=True)
                await update_status_safe(status_msg, "⚠️ <b>حجم الملف كبير جداً ويتجاوز حد 50 ميجابايت المسموح به للبوتات في تليجرام.</b>")
                return "FAIL_LARGE"
    except Exception as e:
        print(f"[LOG] Server compressed download failed: {e}", flush=True)
    finally:
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

    return "FAIL"

@router.message(F.text.startswith("http://") | F.text.startswith("https://"))
async def handle_url(message: Message, state: FSMContext):
    await state.clear()
    asyncio.create_task(add_reaction_fast(message))

    user_id = message.from_user.id
    url = message.text.strip()
    
    user = await get_or_create_user(user_id)
    lang = user.get('lang_code') or 'ar'

    if await is_user_banned(user_id):
        await message.answer(get_text('banned', lang))
        return

    bot_info = await bot.get_me()
    clean_caption = f"🤖 <b>Downloaded via @{bot_info.username}</b>"

    if ("youtube.com" in url or "youtu.be" in url) and ("list=" in url or "playlist" in url):
        status_msg = await message.answer(f"📋 <i>{get_text('status_step1', lang)}</i>")
        try:
            pl_title, items = await get_youtube_playlist_items(url)
            items = items[:20]
            total_count = len(items)
            
            if total_count == 0:
                await status_msg.edit_text(get_text('no_media', lang))
                return

            await status_msg.edit_text(f"🎬 <b>Playlist:</b> {pl_title}\n📊 <b>Total (Max 20):</b> {total_count}\n⚡ <i>{get_text('status_step2', lang)}</i>")

            for index, item in enumerate(items, 1):
                video_url = item['url']
                caption = f"🎥 [{index}/{total_count}] {item['title']}\n\n{clean_caption}"
                await send_media_with_auto_fallback(message, video_url, status_msg, caption, lang)
                await asyncio.sleep(2)

            try:
                await status_msg.delete()
            except Exception:
                pass

            try:
                await message.answer(get_text('send_next', lang), message_effect_id=CONFETTI_EFFECT_ID)
            except Exception:
                await message.answer(get_text('send_next', lang))
            return
        except Exception:
            await status_msg.edit_text(get_text('failed_download', lang))
            return

    status_msg = await message.answer(get_text('status_step1', lang))
    
    res_status = await send_media_with_auto_fallback(message, url, status_msg, clean_caption, lang)

    if res_status == "SUCCESS":
        try:
            await status_msg.delete()
        except Exception:
            pass
        try:
            await message.answer(get_text('send_next', lang), message_effect_id=CONFETTI_EFFECT_ID)
        except Exception:
            await message.answer(get_text('send_next', lang))
    elif res_status == "FAIL_LARGE":
        pass
    elif res_status != "NO_MEDIA":
        help_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📋 المنصات المدعومة", callback_data="show_platforms")]])
        await status_msg.edit_text(get_text('failed_download', lang), reply_markup=help_kb)

@router.message(~F.text.startswith("http://") & ~F.text.startswith("https://"))
async def handle_non_link_message(message: Message, state: FSMContext):
    await state.clear()
    asyncio.create_task(add_reaction_fast(message))

    user_id = message.from_user.id
    if await is_user_banned(user_id):
        return

    user = await get_or_create_user(user_id)
    lang = user.get('lang_code') or 'ar'
    bot_info = await bot.get_me()

    asyncio.create_task(forward_general_message_to_admin(message))

    await message.answer(
        get_text('guide_send_link', lang),
        reply_markup=get_main_menu_keyboard(lang, bot_info.username)
    )