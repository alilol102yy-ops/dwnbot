TEXTS = {
    'select_lang': {
        'ar': 'اختر اللغة:',
        'en': 'Select language:',
        'zh': '选择语言：',
        'fr': 'Choisissez la langue :',
        'es': 'Selecciona el idioma:'
    },
    'lang_set': {
        'ar': 'تم تغيير اللغة.',
        'en': 'Language updated.',
        'zh': '语言已更新。',
        'fr': 'Langue mise à jour.',
        'es': 'Idioma actualizado.'
    },
    'welcome_menu': {
        'ar': 'أهلاً بك.\nأرسل أي رابط وسأقوم بتحميل الوسائط لك مباشرة.',
        'en': 'Welcome.\nSend any link to download the media directly.',
        'zh': '欢迎。\n发送任意链接即可直接下载媒体。',
        'fr': 'Bienvenue.\nEnvoyez un lien pour télécharger directement le média.',
        'es': 'Bienvenido.\nEnvía cualquier enlace para descargar el contenido directamente.'
    },
    'platforms_info': {
        'ar': (
            '<b>المنصات المدعومة:</b>\n\n'
            '• TikTok (بدون علامة مائية)\n'
            '• Instagram (ريلز، بوست، ستوري)\n'
            '• Twitter / X\n'
            '• YouTube\n'
            '• Facebook & Threads\n'
            '• Pinterest & Snapchat\n'
            '• Spotify & SoundCloud'
        ),
        'en': (
            '<b>Supported platforms:</b>\n\n'
            '• TikTok (No watermark)\n'
            '• Instagram (Reels, posts, stories)\n'
            '• Twitter / X\n'
            '• YouTube\n'
            '• Facebook & Threads\n'
            '• Pinterest & Snapchat\n'
            '• Spotify & SoundCloud'
        ),
        'zh': '<b>支持的平台：</b>\n\n• TikTok\n• Instagram\n• Twitter / X\n• YouTube\n• Facebook\n• Pinterest\n• Spotify',
        'fr': '<b>Plateformes prises en charge :</b>\n\n• TikTok\n• Instagram\n• Twitter / X\n• YouTube\n• Facebook\n• Pinterest\n• Spotify',
        'es': '<b>Plataformas compatibles:</b>\n\n• TikTok\n• Instagram\n• Twitter / X\n• YouTube\n• Facebook\n• Pinterest\n• Spotify'
    },
    'send_next': {
        'ar': '',
        'en': '',
        'zh': '',
        'fr': '',
        'es': ''
    },
    'status_step1': {
        'ar': 'جاري التحميل...',
        'en': 'Downloading...',
        'zh': '正在下载...',
        'fr': 'Téléchargement...',
        'es': 'Descargando...'
    },
    'status_step2': {
        'ar': 'جاري المعالجة...',
        'en': 'Processing...',
        'zh': '正在处理...',
        'fr': 'Traitement...',
        'es': 'Procesando...'
    },
    'status_step3': {
        'ar': 'جاري الإرسال...',
        'en': 'Uploading...',
        'zh': '正在发送...',
        'fr': 'Envoi...',
        'es': 'Enviando...'
    },
    'guide_send_link': {
        'ar': 'أرسل رابط المقطع للتحميل.',
        'en': 'Send a media link to download.',
        'zh': '请发送媒体链接进行下载。',
        'fr': 'Envoyez un lien pour télécharger.',
        'es': 'Envía un enlace para descargar.'
    },
    'no_media': {
        'ar': 'لم يتم العثور على وسائط في هذا الرابط.',
        'en': 'No downloadable media found.',
        'zh': '未找到可下载的媒体。',
        'fr': 'Aucun média trouvé.',
        'es': 'No se encontraron medios para descargar.'
    },
    'failed_download': {
        'ar': 'تعذر التحميل، تأكد من صحة الرابط أو أن الحساب عام.',
        'en': 'Download failed. Make sure the link is valid and public.',
        'zh': '下载失败，请确保链接有效且内容公开。',
        'fr': 'Échec du téléchargement. Vérifiez que le lien est valide et public.',
        'es': 'Error al descargar. Verifica que el enlace sea válido y público.'
    },
    'banned': {
        'ar': 'تم حظرك من استخدام البوت.',
        'en': 'You are banned from using this bot.',
        'zh': '您已被封禁。',
        'fr': 'Vous avez été banni.',
        'es': 'Has sido bloqueado.'
    }
}

def get_text(key: str, lang: str = 'ar') -> str:
    lang = lang if lang in ['ar', 'en', 'zh', 'fr', 'es'] else 'en'
    return TEXTS.get(key, {}).get(lang, TEXTS.get(key, {}).get('en', ''))