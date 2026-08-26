import aiohttp
import asyncio
import re
import os
import html
import urllib.parse
import ipaddress
import uuid
import yt_dlp
from config import YOUTUBE_PROXY, YOUTUBE_API_KEY

DOWNLOAD_SEMAPHORE = asyncio.Semaphore(5)

# تعبيرات نمطية دقيقة لمطابقة الكلمات الحساسة فقط بدون الإيجابيات الكاذبة
SENSITIVE_PATTERNS = [
    re.compile(r'\b(?:nsfw|18\+|adult|porn|porno|pornography|sex|sexy|erotic|nude|nudes|naked|hentai|boobs|dick|pussy|cum|milf|slut|whore)\b', re.IGNORECASE),
    re.compile(r'\b(?:xnxx|xvideos|pornhub|onlyfans|brazzers)\b', re.IGNORECASE),
    re.compile(r'(?:سكس|اباحي|إباحي|تعري|نيك|طيز|ديوث|شرج|قحبه|قحبة)')
]

def is_safe_url(url: str) -> bool:
    """التحقق الأمني الشامل من الروابط لمنع هجمات SSRF واستهداف الشبكات الداخلية"""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme not in ('http', 'https'):
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        hostname_clean = hostname.lower().strip("[]")
        
        # فحص إذا كان المضيف عنوان IP
        try:
            ip_obj = ipaddress.ip_address(hostname_clean)
            if (ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local or 
                ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified):
                return False
        except ValueError:
            # اسم نطاق عادي
            blocked_domains = ("localhost", "localtest.me", "127.0.0.1", "0.0.0.0", "metadata.google.internal")
            if any(hostname_clean == d or hostname_clean.endswith(f".{d}") for d in blocked_domains):
                return False

        return True
    except Exception:
        return False

def get_cookie_file(url: str) -> str | None:
    if ("instagram.com" in url or "instagr.am" in url) and os.path.exists("inscookies.txt"):
        return "inscookies.txt"
    elif ("facebook.com" in url or "fb.watch" in url or "fb.com" in url) and os.path.exists("fcookies.txt"):
        return "fcookies.txt"
    elif os.path.exists("cookies.txt"):
        return "cookies.txt"
    return None

def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[^\w\s]', ' ', re.sub(r'[أإآا]', 'ا', text))

def check_sensitivity(text: str) -> bool:
    if not text:
        return False
    norm = normalize_text(text)
    return any(p.search(norm) is not None for p in SENSITIVE_PATTERNS)

def extract_youtube_id(url: str) -> str | None:
    match_v = re.search(r"[?&]v=([0-9A-Za-z_-]{11})", url)
    if match_v:
        return match_v.group(1)
    match_short = re.search(r"(?:youtu\.be\/|shorts\/|embed\/|v\/)([0-9A-Za-z_-]{11})", url)
    if match_short:
        return match_short.group(1)
    return None

# ==========================================
# 1. تحويل سبوتيفاي إلى يوتيوب
# ==========================================
async def resolve_spotify_track(spotify_url: str) -> str | None:
    try:
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(spotify_url)}"
        async with aiohttp.ClientSession() as session:
            async with session.get(oembed_url, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    title = data.get("title", "")
                    artist = data.get("author_name", "")
                    query = f"{artist} {title} audio"
                    
                    if YOUTUBE_API_KEY:
                        s_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={urllib.parse.quote(query)}&type=video&maxResults=1&key={YOUTUBE_API_KEY}"
                        async with session.get(s_url, timeout=8) as yt_resp:
                            if yt_resp.status == 200:
                                yt_data = await yt_resp.json()
                                items = yt_data.get('items', [])
                                if items:
                                    return f"https://www.youtube.com/watch?v={items[0]['id']['videoId']}"
    except Exception as e:
        print(f"[LOG] Spotify Resolve Error: {e}", flush=True)
    return None

async def get_youtube_playlist_items(playlist_url: str):
    if not YOUTUBE_API_KEY:
        raise Exception("YOUTUBE_API_KEY is missing!")
    match = re.search(r"list=([0-9A-Za-z_-]+)", playlist_url)
    if not match:
        raise Exception("Invalid Playlist URL")
    url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={match.group(1)}&maxResults=20&key={YOUTUBE_API_KEY}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                return "YouTube Playlist", [{"url": f"https://www.youtube.com/watch?v={i['snippet']['resourceId']['videoId']}", "title": html.unescape(i['snippet']['title'])} for i in data.get('items', [])]
    raise Exception("Failed to fetch playlist")

# ==========================================
# 2. الروابط المباشرة السريعة (تيك توك وتويتر وإنستغرام)
# ==========================================
async def get_direct_stream_url(url: str):
    if not is_safe_url(url):
        return "NO_MEDIA", "none", False, None, None
    is_audio = "spotify.com" in url or "soundcloud.com" in url

    if "youtube.com" in url or "youtu.be" in url or "spotify.com" in url:
        return None, "video", False, None, None

    async with aiohttp.ClientSession() as session:
        # تويتر / X
        if "twitter.com" in url or "x.com" in url:
            match = re.search(r'status/(\d+)', url)
            if match:
                try:
                    async with session.get(f"https://api.vxtwitter.com/status/{match.group(1)}", timeout=5) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            media_list = d.get("media_extended", [])
                            vids = [m["url"] for m in media_list if m.get("type") in ["video", "gif"]]
                            if vids:
                                return vids[0], "audio" if is_audio else "video", d.get("possibly_sensitive", False), d.get("text", "Twitter Video"), "X / Twitter"
                            photos = [m["url"] for m in media_list if m.get("type") in ["image", "photo"]]
                            if photos:
                                return photos, "photo", d.get("possibly_sensitive", False), d.get("text", "Twitter Photo"), "X / Twitter"
                except Exception:
                    pass

    return None, "video", False, None, None

# ==========================================
# 3. محرك Loader.to المباشر السريع جداً
# ==========================================
async def fetch_from_loader_to(url: str, is_audio: bool) -> str | None:
    fmt = "mp3" if is_audio else "360"
    api_init = f"https://loader.to/ajax/download.php?format={fmt}&url={urllib.parse.quote(url)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://loader.to/"
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_init, headers=headers, timeout=8) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    job_id = data.get("id")
                    if job_id:
                        progress_url = f"https://loader.to/ajax/progress.php?id={job_id}"
                        for attempt in range(20):
                            await asyncio.sleep(1)
                            try:
                                async with session.get(progress_url, headers=headers, timeout=5) as p_resp:
                                    if p_resp.status == 200:
                                        p_data = await p_resp.json()
                                        d_url = p_data.get("download_url") or p_data.get("url")
                                        if d_url:
                                            return d_url
                                        if p_data.get("text") == "Error" or (p_data.get("success") == 0 and p_data.get("text") == "Invalid URL"):
                                            break
                            except Exception:
                                continue
        except Exception as e:
            print(f"[LOG] Loader.to Error: {e}", flush=True)
            
    return None

# ==========================================
# 4. محرك Cobalt API المباشر
# ==========================================
async def fetch_from_cobalt_api(url: str, is_audio: bool):
    payload = {
        "url": url,
        "downloadMode": "audio" if is_audio else "auto",
        "videoQuality": "360"
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    cobalt_instances = [
        "https://api.cobalt.tools",
        "https://co.wuk.sh",
        "https://cobalt.canine.tools",
        "https://cobalt.meowing.de"
    ]
    
    proxy_opts = [YOUTUBE_PROXY, None] if YOUTUBE_PROXY else [None]

    async with aiohttp.ClientSession() as session:
        for p_opt in proxy_opts:
            for instance in cobalt_instances:
                try:
                    async with session.post(f"{instance}/", json=payload, headers=headers, proxy=p_opt, timeout=6) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if "url" in data and data["url"]:
                                return data["url"]
                except Exception:
                    continue
    return None

# ==========================================
# 5. دالة فك الروابط المختصرة
# ==========================================
async def expand_short_url(url: str) -> str:
    """فك الروابط المختصرة (مثل vt.tiktok.com أو vm.tiktok.com) للحصول على الرابط الكامل"""
    if any(s in url for s in ("vt.tiktok.com", "vm.tiktok.com", "/t/", "v.douyin.com")):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with aiohttp.ClientSession() as session:
                async with session.get(url, allow_redirects=True, headers=headers, timeout=6) as resp:
                    if resp.url:
                        return str(resp.url)
        except Exception:
            pass
    return url

# ==========================================
# 6. محرك التنزيل الشامل
# ==========================================
async def download_local_compressed(url: str, output_dir: str = "downloads"):
    os.makedirs(output_dir, exist_ok=True)
    
    # فك الروابط المختصرة أولاً
    url = await expand_short_url(url)
    
    is_audio = "spotify.com" in url or "soundcloud.com" in url

    if "spotify.com" in url:
        yt_url = await resolve_spotify_track(url)
        if yt_url:
            url = yt_url
            is_audio = True
        else:
            raise Exception("تعذر العثور على الأغنية في يوتيوب من رابط سبوتيفاي.")

    async with DOWNLOAD_SEMAPHORE:
        file_prefix = f"media_{uuid.uuid4().hex[:8]}"
        filepath = f"{output_dir}/{file_prefix}.{'mp3' if is_audio else 'mp4'}"

        # 🟢 محرك تيك توك فائق الصمود (TikWM Multi-Domain + TikMate Fallback)
        if "tiktok.com" in url or "douyin.com" in url:
            tt_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9"
            }
            
            # استخراج الآيدي الرقمي للفيديو لضمان قبول الـ API
            tt_match = re.search(r'(\d{17,21})', url)
            clean_tt_url = f"https://www.tiktok.com/@i/video/{tt_match.group(1)}" if tt_match else url

            # 1. المحاولة عبر نطاقات TikWM المتعددة مع إعادة المحاولة الذكية
            for domain in ["www.tikwm.com", "api.tikwm.com"]:
                try:
                    print(f"[LOG] Fetching TikTok media via {domain}...", flush=True)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"https://{domain}/api/?url={urllib.parse.quote(clean_tt_url)}", headers=tt_headers, timeout=10) as resp:
                            if resp.status == 200:
                                res_json = await resp.json()
                                if res_json.get("code") == 0:
                                    d = res_json.get("data", {})
                                    media_url = d.get("music") if is_audio else (d.get("play") or d.get("wmplay"))
                                    title = d.get("title", "TikTok Media")
                                    author = d.get("author", {}).get("nickname", "TikTok")
                                    
                                    if media_url:
                                        async with session.get(media_url, headers=tt_headers, timeout=120) as v_resp:
                                            if v_resp.status == 200:
                                                with open(filepath, 'wb') as f:
                                                    async for chunk in v_resp.content.iter_chunked(2*1024*1024):
                                                        f.write(chunk)
                                                if os.path.exists(filepath) and os.path.getsize(filepath) > 50 * 1024:
                                                    print(f"[LOG] TikTok Media Downloaded via {domain} ({os.path.getsize(filepath)/(1024*1024):.2f}MB)", flush=True)
                                                    return None, filepath, "audio" if is_audio else "video", check_sensitivity(title) or check_sensitivity(url), title, author
                                elif "Limit" in res_json.get("msg", ""):
                                    print(f"[LOG] {domain} rate limited, waiting 1s...", flush=True)
                                    await asyncio.sleep(1)
                except Exception as e:
                    print(f"[LOG] {domain} failed: {e}", flush=True)

            # 2. المحاولة عبر محرك TikMate الاحتياطي
            try:
                print(f"[LOG] Fetching TikTok media via TikMate fallback...", flush=True)
                async with aiohttp.ClientSession() as session:
                    async with session.post("https://api.tikmate.app/api/lookup", data={"url": clean_tt_url}, headers=tt_headers, timeout=10) as resp:
                        if resp.status == 200:
                            d = await resp.json()
                            token = d.get("token")
                            vid_id = d.get("id")
                            if token and vid_id:
                                dl_url = f"https://tikmate.app/download/{token}/{vid_id}.mp4?hd=1"
                                async with session.get(dl_url, headers={"User-Agent": tt_headers["User-Agent"], "Referer": "https://tikmate.app/"}, timeout=120) as v_resp:
                                    if v_resp.status == 200:
                                        with open(filepath, 'wb') as f:
                                            async for chunk in v_resp.content.iter_chunked(2*1024*1024):
                                                f.write(chunk)
                                        if os.path.exists(filepath) and os.path.getsize(filepath) > 50 * 1024:
                                            print(f"[LOG] TikTok Media Downloaded via TikMate ({os.path.getsize(filepath)/(1024*1024):.2f}MB)", flush=True)
                                            return None, filepath, "video", check_sensitivity(url), "TikTok Media", "TikTok"
            except Exception as e:
                print(f"[LOG] TikMate fallback failed: {e}", flush=True)

            raise Exception("تعذر تحميل فيديو تيك توك في الوقت الحالي، يرجى التأكد من أن الحساب عام والمحاولة مرة أخرى.")

        # 🟢 محرك تويتر / X المباشر
        if "twitter.com" in url or "x.com" in url:
            try:
                match = re.search(r'status/(\d+)', url)
                if match:
                    print(f"[LOG] Fetching Twitter/X media via VxTwitter...", flush=True)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"https://api.vxtwitter.com/status/{match.group(1)}", timeout=8) as resp:
                            if resp.status == 200:
                                d = await resp.json()
                                media_list = d.get("media_extended", [])
                                vids = [m["url"] for m in media_list if m.get("type") in ["video", "gif"]]
                                if vids:
                                    async with session.get(vids[0], timeout=120) as v_resp:
                                        if v_resp.status == 200:
                                            with open(filepath, 'wb') as f:
                                                async for chunk in v_resp.content.iter_chunked(2*1024*1024):
                                                    f.write(chunk)
                                            if os.path.exists(filepath) and os.path.getsize(filepath) > 50 * 1024:
                                                return None, filepath, "video", d.get("possibly_sensitive", False), d.get("text", "Twitter Video"), "Twitter"
            except Exception as e:
                print(f"[LOG] Twitter direct download failed: {e}", flush=True)

        # 🟢 محرك يوتيوب المباشر
        if "youtube.com" in url or "youtu.be" in url:
            video_id = extract_youtube_id(url)
            print(f"[LOG] Processing YouTube Link. Extracted Video ID: {video_id}", flush=True)
            dl_url = None

            # 🟢 المحاولة 1: Loader.to API
            dl_url = await fetch_from_loader_to(url, is_audio)

            # 🟢 المحاولة 2: Cobalt API
            if not dl_url:
                dl_url = await fetch_from_cobalt_api(url, is_audio)

            if dl_url:
                try:
                    print(f"[LOG] Downloading stream directly from API...", flush=True)
                    async with aiohttp.ClientSession() as session:
                        async with session.get(dl_url, timeout=120) as resp:
                            ctype = resp.headers.get("Content-Type", "").lower()
                            
                            if resp.status == 200 and "text/html" not in ctype:
                                downloaded_bytes = 0
                                max_allowed = 450 * 1024 * 1024  # 450MB حد أقصى لحماية السيرفر
                                with open(filepath, 'wb') as f:
                                    async for chunk in resp.content.iter_chunked(2*1024*1024):
                                        downloaded_bytes += len(chunk)
                                        if downloaded_bytes > max_allowed:
                                            raise Exception("File exceeds maximum allowed download size.")
                                        f.write(chunk)
                                
                                fsize = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                                if fsize > 100 * 1024:
                                    print(f"[LOG] Valid Video Downloaded Successfully ({fsize / (1024*1024):.2f} MB)", flush=True)
                                    return None, filepath, "audio" if is_audio else "video", check_sensitivity(url), "Media", "Bot"
                                else:
                                    print(f"[LOG] Corrupt download rejected (size too small: {fsize} bytes)", flush=True)
                                    if os.path.exists(filepath):
                                        os.remove(filepath)
                except Exception as e:
                    print(f"[LOG] Stream API Download failed: {e}", flush=True)
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass

        # 🟡 المحاولة 3: yt-dlp التنزيل المحلي الاحتياطي
        out_template = f"{output_dir}/{file_prefix}.%(ext)s"
        ydl_opts = {
            'format': 'bestaudio/best' if is_audio else 'best[height<=720][ext=mp4]/best[ext=mp4]/best',
            'outtmpl': out_template,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'socket_timeout': 20,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            }
        }
        
        cookie_file = get_cookie_file(url)
        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Media')
                uploader = info.get('uploader', 'Unknown')
                
                # البحث عن الملف المحفوظ الفعلي لتحديد نوعه وامتداده
                actual_file = None
                for fname in os.listdir(output_dir):
                    if fname.startswith(file_prefix):
                        actual_file = os.path.join(output_dir, fname)
                        break
                
                if not actual_file:
                    actual_file = filepath

                file_ext = os.path.splitext(actual_file)[1].lower()
                m_type = "audio" if (is_audio or file_ext in ['.mp3', '.m4a', '.aac', '.ogg', '.opus', '.wav']) else "video"
                if file_ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    m_type = "photo"

                sens = check_sensitivity(title) or check_sensitivity(url)
                return info, actual_file, m_type, sens, title, uploader

        return await asyncio.to_thread(_download)