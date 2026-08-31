from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database import get_or_create_user, set_user_language, is_user_banned
from keyboards.inline import get_language_keyboard, get_main_menu_keyboard, get_back_keyboard
from locales.translations import get_text
from config import bot

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    
    user_id = message.from_user.id
    if await is_user_banned(user_id):
        await message.answer(get_text('banned', 'ar'))
        return

    user = await get_or_create_user(user_id)
    lang_code = user.get('lang_code')
    bot_info = await bot.get_me()

    if not lang_code:
        await message.answer(
            get_text('select_lang', 'en'),
            reply_markup=get_language_keyboard()
        )
        return

    await message.answer(
        get_text('welcome_menu', lang_code),
        reply_markup=get_main_menu_keyboard(lang_code, bot_info.username)
    )

@router.message(Command("lang"))
async def cmd_lang(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        get_text('select_lang', 'en'),
        reply_markup=get_language_keyboard()
    )

@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    user = await get_or_create_user(user_id)
    lang = user.get('lang_code') or 'ar'
    
    await message.answer(
        get_text('platforms_info', lang),
        reply_markup=get_back_keyboard(lang)
    )

@router.callback_query(F.data.startswith("set_lang:"))
async def process_language_selection(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    lang_code = callback.data.split(":")[1]

    await set_user_language(user_id, lang_code)
    bot_info = await bot.get_me()

    try:
        await callback.answer()
    except Exception:
        pass

    try:
        await callback.message.edit_text(
            f"{get_text('lang_set', lang_code)}\n\n{get_text('welcome_menu', lang_code)}",
            reply_markup=get_main_menu_keyboard(lang_code, bot_info.username)
        )
    except Exception:
        pass

@router.callback_query(F.data == "change_lang")
async def process_change_lang_request(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await callback.message.edit_text(
            get_text('select_lang', 'en'),
            reply_markup=get_language_keyboard()
        )
    except Exception:
        pass

@router.callback_query(F.data == "show_platforms")
async def process_show_platforms(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    user = await get_or_create_user(user_id)
    lang = user.get('lang_code') or 'ar'

    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await callback.message.edit_text(
            get_text('platforms_info', lang),
            reply_markup=get_back_keyboard(lang)
        )
    except Exception:
        pass

@router.callback_query(F.data == "back_to_main")
async def process_back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    user = await get_or_create_user(user_id)
    lang = user.get('lang_code') or 'ar'
    bot_info = await bot.get_me()

    try:
        await callback.answer()
    except Exception:
        pass
    try:
        await callback.message.edit_text(
            get_text('welcome_menu', lang),
            reply_markup=get_main_menu_keyboard(lang, bot_info.username)
        )
    except Exception:
        pass