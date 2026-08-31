from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUPPORTED_LANGUAGES

def get_language_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for lang_code, lang_name in SUPPORTED_LANGUAGES.items():
        buttons.append([InlineKeyboardButton(text=lang_name, callback_data=f"set_lang:{lang_code}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_main_menu_keyboard(lang_code: str, bot_username: str = "") -> InlineKeyboardMarkup:
    text_map = {
        'ar': ("🌐 اللغة", "📋 المنصات", "↗️ مشاركة"),
        'en': ("🌐 Language", "📋 Platforms", "↗️ Share"),
        'zh': ("🌐 语言", "📋 支持平台", "↗️ 分享"),
        'fr': ("🌐 Langue", "📋 Plateformes", "↗️ Partager"),
        'es': ("🌐 Idioma", "📋 Plataformas", "↗️ Compartir"),
    }
    lang_btn, plat_btn, share_btn = text_map.get(lang_code, text_map['en'])
    share_url = f"https://t.me/share/url?url=https://t.me/{bot_username}&text=Fastest%20all-in-one%20HD%20Media%20Downloader%20⚡"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=plat_btn, callback_data="show_platforms")],
        [InlineKeyboardButton(text=lang_btn, callback_data="change_lang"), InlineKeyboardButton(text=share_btn, url=share_url)]
    ])

def get_back_keyboard(lang_code: str) -> InlineKeyboardMarkup:
    back_map = {
        'ar': "🔙 رجوع",
        'en': "🔙 Back",
        'zh': "🔙 返回",
        'fr': "🔙 Retour",
        'es': "🔙 Volver",
    }
    back_btn = back_map.get(lang_code, "🔙 Back")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=back_btn, callback_data="back_to_main")]
    ])