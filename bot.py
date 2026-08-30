import os
import asyncio
import shutil
import subprocess

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp


# ==================================================
# Environment
# ==================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError(
        "ไม่พบ DISCORD_TOKEN ใน Environment Variables"
    )


# ==================================================
# Discord Intents
# ==================================================

intents = discord.Intents.default()
intents.message_content = True


# ==================================================
# Bot
# ==================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==================================================
# Paths
# ==================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

COOKIES_FILE = os.path.join(
    BASE_DIR,
    "cookies.txt"
)

# Hosting ของป๊อป
DENO_PATH = "/home/container/deno"


# ==================================================
# Find Deno
# ==================================================

def find_deno():

    # 1. ตำแหน่งที่ Hosting ของป๊อปใช้
    if os.path.isfile(DENO_PATH):

        return DENO_PATH

    # 2. PATH
    deno = shutil.which("deno")

    if deno:

        return deno

    # 3. Local
    local_paths = [
        os.path.join(BASE_DIR, "deno"),
        os.path.join(BASE_DIR, "bin", "deno"),
        "/home/container/bin/deno",
        "/usr/local/bin/deno",
        "/usr/bin/deno",
        os.path.expanduser(
            "~/.deno/bin/deno"
        ),
    ]

    for path in local_paths:

        if os.path.isfile(path):

            return path

    return None


DENO_EXECUTABLE = find_deno()


# ==================================================
# Runtime Status
# ==================================================

def print_runtime_status():

    print("=" * 60)
    print("🧩 JavaScript Runtime")
    print("=" * 60)

    if not DENO_EXECUTABLE:

        print("❌ ไม่พบ Deno")

        print(
            "⚠️ YouTube อาจไม่สามารถแก้ EJS challenge ได้"
        )

        print("=" * 60)

        return False

    print("🦕 พบ Deno")

    print(
        f"📁 Path: {DENO_EXECUTABLE}"
    )

    try:

        result = subprocess.run(
            [
                DENO_EXECUTABLE,
                "--version"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = (
            result.stdout.strip()
            or result.stderr.strip()
        )

        if output:

            print(
                f"📦 Version:\n{output}"
            )

    except Exception as e:

        print(
            f"⚠️ ตรวจสอบ Deno ไม่สำเร็จ: {e}"
        )

    print("=" * 60)

    return True


# ==================================================
# yt-dlp Base Options
# ==================================================

YTDL_BASE_OPTIONS = {

    # ไม่ดาวน์โหลดไฟล์
    "skip_download": True,

    # ไม่เอา Playlist
    "noplaylist": True,

    # Network
    "source_address": "0.0.0.0",

    "geo_bypass": True,

    "nocheckcertificate": True,

    # Retry
    "retries": 3,

    "fragment_retries": 3,

    "socket_timeout": 20,

    # EJS
    #
    # Deno รองรับการดาวน์โหลด yt-dlp-ejs
    # จาก npm
    #
    "remote_components": [
        "ejs:npm"
    ],

}


# ==================================================
# Deno Configuration
# ==================================================

if DENO_EXECUTABLE:

    YTDL_BASE_OPTIONS["js_runtimes"] = {
        "deno": {
            "path": DENO_EXECUTABLE
        }
    }


# ==================================================
# Cookies
# ==================================================

if os.path.isfile(COOKIES_FILE):

    YTDL_BASE_OPTIONS["cookiefile"] = (
        COOKIES_FILE
    )

    print("=" * 60)

    print("🍪 พบ cookies.txt")

    print(
        f"📁 {COOKIES_FILE}"
    )

    print("=" * 60)

else:

    print("=" * 60)

    print("ℹ️ ไม่พบ cookies.txt")

    print(
        "ℹ️ Bot จะทำงานโดยไม่ใช้ Cookies"
    )

    print("=" * 60)


# ==================================================
# FFmpeg
# ==================================================

FFMPEG_OPTIONS = {

    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5 "
        "-nostdin"
    ),

    "options": "-vn",

}


# ==================================================
# Queue
# ==================================================

music_queue = []

current_song = None


# ==================================================
# Check FFmpeg
# ==================================================

async def check_ffmpeg():

    ffmpeg_path = shutil.which(
        "ffmpeg"
    )

    print("=" * 60)

    if ffmpeg_path:

        print("✅ พบ FFmpeg")

        print(
            f"📁 Path: {ffmpeg_path}"
        )

    else:

        print("❌ ไม่พบ FFmpeg")

    print("=" * 60)


# ==================================================
# Extract Direct Audio URL
# ==================================================

def extract_direct_url(webpage_url):

    """
    ดึง Audio URL จาก YouTube โดยตรง

    พยายามหลาย format
    """

    formats = [

        # Audio ปกติ
        "bestaudio/best",

        # Audio สำรอง
        "bestaudio[ext=m4a]/bestaudio",

        # Format 18
        "18",

        # fallback
        "best",

    ]

    last_error = None

    for format_selector in formats:

        print("=" * 60)

        print(
            f"🎧 ทดลอง format: {format_selector}"
        )

        print("=" * 60)

        options = YTDL_BASE_OPTIONS.copy()

        options["format"] = format_selector

        options["quiet"] = True

        options["no_warnings"] = False

        try:

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    webpage_url,
                    download=False
                )

                if not info:

                    continue

                # --------------------------------------------------
                # ถ้ามี URL ตรง
                # --------------------------------------------------

                audio_url = info.get(
                    "url"
                )

                if audio_url:

                    print(
                        "✅ พบ Direct Audio URL"
                    )

                    return {
                        "title": info.get(
                            "title",
                            "Unknown"
                        ),
                        "url": audio_url,
                        "webpage_url": info.get(
                            "webpage_url",
                            webpage_url
                        ),
                        "duration": info.get(
                            "duration"
                        ),
                        "thumbnail": info.get(
                            "thumbnail"
                        ),
                    }

                # --------------------------------------------------
                # ถ้าไม่มี URL ลองหา formats
                # --------------------------------------------------

                available_formats = (
                    info.get("formats")
                    or []
                )

                # หา audio ก่อน
                audio_formats = [
                    f
                    for f in available_formats
                    if f.get("url")
                    and (
                        f.get("vcodec") == "none"
                        or f.get("acodec") != "none"
                    )
                ]

                if audio_formats:

                    # เอาตัวท้าย/คุณภาพดีที่สุด
                    selected = audio_formats[-1]

                    audio_url = selected.get(
                        "url"
                    )

                    if audio_url:

                        print(
                            "✅ พบ Audio URL จาก formats"
                        )

                        return {
                            "title": info.get(
                                "title",
                                "Unknown"
                            ),
                            "url": audio_url,
                            "webpage_url": info.get(
                                "webpage_url",
                                webpage_url
                            ),
                            "duration": info.get(
                                "duration"
                            ),
                            "thumbnail": info.get(
                                "thumbnail"
                            ),
                        }

        except Exception as e:

            last_error = e

            print(
                f"⚠️ format {format_selector} ไม่สำเร็จ"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

    if last_error:

        raise last_error

    raise RuntimeError(
        "ไม่พบ Audio URL จาก YouTube"
    )


# ==================================================
# Search YouTube
# ==================================================

async def search_song(search):

    loop = asyncio.get_running_loop()

    def extract():

        print("=" * 60)

        print(
            f"🔎 กำลังค้นหา: {search}"
        )

        print("=" * 60)

        # --------------------------------------------------
        # สำคัญ:
        # Search ใช้ extract_flat
        # เพื่อไม่ให้ yt-dlp พยายามเลือก audio
        # ตั้งแต่ขั้นตอนค้นหา
        # --------------------------------------------------

        search_options = (
            YTDL_BASE_OPTIONS.copy()
        )

        search_options.pop(
            "skip_download",
            None
        )

        search_options["extract_flat"] = True

        search_options["quiet"] = True

        search_options["no_warnings"] = False

        search_options["default_search"] = (
            "ytsearch1"
        )

        with yt_dlp.YoutubeDL(
            search_options
        ) as ydl:

            info = ydl.extract_info(
                f"ytsearch1:{search}",
                download=False
            )

        if not info:

            return None

        entries = info.get(
            "entries"
        )

        if not entries:

            return None

        song = entries[0]

        if not song:

            return None

        title = song.get(
            "title",
            search
        )

        webpage_url = song.get(
            "webpage_url"
        )

        # บางกรณี flat extraction
        # อาจคืน URL เป็น id
        if not webpage_url:

            video_id = song.get(
                "id"
            )

            if video_id:

                webpage_url = (
                    f"https://www.youtube.com/watch?v={video_id}"
                )

        if not webpage_url:

            raise RuntimeError(
                "ค้นหาเจอเพลง แต่ไม่พบ YouTube URL"
            )

        print("=" * 60)

        print("✅ พบเพลง")

        print(
            f"🎵 {title}"
        )

        print(
            f"🔗 {webpage_url}"
        )

        print("=" * 60)

        # --------------------------------------------------
        # ดึง Audio URL จริง
        # --------------------------------------------------

        direct_song = extract_direct_url(
            webpage_url
        )

        if not direct_song:

            raise RuntimeError(
                "ไม่สามารถดึง Audio URL ได้"
            )

        direct_song["title"] = (
            direct_song.get(
                "title",
                title
            )
        )

        direct_song["webpage_url"] = (
            direct_song.get(
                "webpage_url",
                webpage_url
            )
        )

        return direct_song

    try:

        return await loop.run_in_executor(
            None,
            extract
        )

    except Exception as e:

        print("=" * 60)

        print("❌ SEARCH ERROR")

        print(
            f"{type(e).__name__}: {e}"
        )

        print("=" * 60)

        raise


# ==================================================
# Play Next
# ==================================================

async def play_next(ctx):

    global current_song

    voice = ctx.voice_client

    if voice is None:

        current_song = None

        return

    if not music_queue:

        current_song = None

        await ctx.send(
            "📭 เพลงในคิวหมดแล้วครับ"
        )

        return

    current_song = music_queue.pop(
        0
    )

    title = current_song[
        "title"
    ]

    audio_url = current_song[
        "url"
    ]

    try:

        source = discord.FFmpegPCMAudio(
            audio_url,
            executable="ffmpeg",
            **FFMPEG_OPTIONS
        )

    except Exception as e:

        print("=" * 60)

        print("❌ FFMPEG SOURCE ERROR")

        print(
            f"{type(e).__name__}: {e}"
        )

        print("=" * 60)

        await ctx.send(
            "❌ เปิด Audio Stream ไม่ได้ครับ\n"
            f"`{type(e).__name__}: {e}`"
        )

        current_song = None

        # ไปเพลงถัดไป
        if music_queue:

            await play_next(ctx)

        return

    # --------------------------------------------------
    # Callback
    # --------------------------------------------------

    def after_playing(error):

        if error:

            print(
                f"❌ Audio Error: {error}"
            )

        future = asyncio.run_coroutine_threadsafe(
            play_next(ctx),
            bot.loop
        )

        try:

            future.result(
                timeout=60
            )

        except Exception as callback_error:

            print(
                "❌ PLAY NEXT ERROR:",
                callback_error
            )

    # --------------------------------------------------
    # Play
    # --------------------------------------------------

    try:

        voice.play(
            source,
            after=after_playing
        )

    except Exception as e:

        print("=" * 60)

        print("❌ VOICE PLAY ERROR")

        print(
            f"{type(e).__name__}: {e}"
        )

        print("=" * 60)

        await ctx.send(
            "❌ เล่นเพลงไม่ได้ครับ\n"
            f"`{type(e).__name__}: {e}`"
        )

        current_song = None

        return

    await ctx.send(
        f"🎵 กำลังเล่น **{title}**"
    )


# ==================================================
# Ready
# ==================================================

@bot.event
async def on_ready():

    print("=" * 60)

    print(
        "🚀 DJ Pop พร้อมใช้งาน"
    )

    print("=" * 60)

    print(
        f"✅ Login สำเร็จ: {bot.user}"
    )

    print(
        f"🆔 Bot ID: {bot.user.id}"
    )

    print("=" * 60)

    print("📋 Commands:")

    for command in bot.commands:

        print(
            f"   !{command.name}"
        )

    print("=" * 60)

    print(
        f"📦 yt-dlp version: "
        f"{yt_dlp.version.__version__}"
    )

    print_runtime_status()

    await check_ffmpeg()


# ==================================================
# !ping
# ==================================================

@bot.command()
async def ping(ctx):

    await ctx.send(
        "🏓 Pong!"
    )


# ==================================================
# !join
# ==================================================

@bot.command()
async def join(ctx):

    if ctx.author.voice is None:

        await ctx.send(
            "❌ ป๊อปต้องเข้าห้องพูดก่อนครับ"
        )

        return

    channel = (
        ctx.author.voice.channel
    )

    try:

        if ctx.voice_client:

            await ctx.voice_client.move_to(
                channel
            )

        else:

            await channel.connect()

        await ctx.send(
            f"🎤 DJ Pop เข้าห้อง "
            f"**{channel.name}** แล้วครับ!"
        )

    except Exception as e:

        print("=" * 60)

        print("❌ JOIN ERROR")

        print(
            f"{type(e).__name__}: {e}"
        )

        print("=" * 60)

        await ctx.send(
            "❌ Bot เข้าห้องไม่ได้ครับ\n"
            f"`{type(e).__name__}: {e}`"
        )


# ==================================================
# !play
# ==================================================

@bot.command()
async def play(ctx, *, search):

    if ctx.author.voice is None:

        await ctx.send(
            "❌ ป๊อปต้องเข้าห้องพูดก่อนครับ"
        )

        return

    # --------------------------------------------------
    # Connect
    # --------------------------------------------------

    if ctx.voice_client is None:

        try:

            await ctx.author.voice.channel.connect()

        except Exception as e:

            await ctx.send(
                "❌ Bot เข้า Voice ไม่ได้ครับ\n"
                f"`{type(e).__name__}: {e}`"
            )

            return

    voice = ctx.voice_client

    # --------------------------------------------------
    # Search Message
    # --------------------------------------------------

    message = await ctx.send(
        f"🔎 กำลังค้นหา **{search}** ..."
    )

    try:

        song = await search_song(
            search
        )

        if song is None:

            await message.edit(
                content="❌ หาเพลงไม่เจอครับ"
            )

            return

        # --------------------------------------------------
        # Queue
        # --------------------------------------------------

        if (
            voice.is_playing()
            or voice.is_paused()
        ):

            music_queue.append(
                song
            )

            await message.edit(
                content=(
                    "📋 เพิ่มเข้าคิวแล้ว\n"
                    f"🎵 **{song['title']}**\n"
                    f"ลำดับที่ "
                    f"**{len(music_queue)}**"
                )
            )

            return

        music_queue.append(
            song
        )

        try:

            await message.delete()

        except Exception:

            pass

        await play_next(ctx)

    except Exception as e:

        print("=" * 60)

        print("❌ PLAY ERROR")

        print(
            f"ประเภท: {type(e).__name__}"
        )

        print(
            f"รายละเอียด: {e}"
        )

        print("=" * 60)

        try:

            await message.edit(
                content=(
                    "❌ เล่นเพลงไม่ได้ครับ\n"
                    f"`{type(e).__name__}: {e}`"
                )
            )

        except Exception:

            pass


# ==================================================
# !skip
# ==================================================

@bot.command()
async def skip(ctx):

    voice = ctx.voice_client

    if voice is None:

        await ctx.send(
            "❌ DJ Pop ไม่ได้อยู่ในห้องพูดครับ"
        )

        return

    if not voice.is_playing():

        await ctx.send(
            "❌ ตอนนี้ไม่มีเพลงกำลังเล่นครับ"
        )

        return

    voice.stop()

    await ctx.send(
        "⏭️ ข้ามเพลงแล้วครับ"
    )


# ==================================================
# !pause
# ==================================================

@bot.command()
async def pause(ctx):

    voice = ctx.voice_client

    if voice is None:

        await ctx.send(
            "❌ DJ Pop ไม่ได้อยู่ในห้องพูดครับ"
        )

        return

    if voice.is_playing():

        voice.pause()

        await ctx.send(
            "⏸️ พักเพลงแล้วครับ"
        )

    else:

        await ctx.send(
            "❌ ตอนนี้ไม่มีเพลงกำลังเล่นครับ"
        )


# ==================================================
# !resume
# ==================================================

@bot.command()
async def resume(ctx):

    voice = ctx.voice_client

    if voice is None:

        await ctx.send(
            "❌ DJ Pop ไม่ได้อยู่ในห้องพูดครับ"
        )

        return

    if voice.is_paused():

        voice.resume()

        await ctx.send(
            "▶️ เล่นเพลงต่อแล้วครับ"
        )

    else:

        await ctx.send(
            "❌ เพลงไม่ได้อยู่ในสถานะพักครับ"
        )


# ==================================================
# !queue
# ==================================================

@bot.command()
async def queue(ctx):

    if not music_queue:

        await ctx.send(
            "📭 ตอนนี้ไม่มีเพลงในคิวครับ"
        )

        return

    text = "📋 **คิวเพลง**\n\n"

    for index, song in enumerate(
        music_queue,
        start=1
    ):

        text += (
            f"**{index}.** "
            f"{song['title']}\n"
        )

    await ctx.send(
        text
    )


# ==================================================
# !nowplaying
# ==================================================

@bot.command()
async def nowplaying(ctx):

    if current_song is None:

        await ctx.send(
            "📭 ตอนนี้ไม่มีเพลงกำลังเล่นครับ"
        )

        return

    await ctx.send(
        "🎵 **กำลังเล่น**\n"
        f"{current_song['title']}"
    )


# ==================================================
# !stop
# ==================================================

@bot.command()
async def stop(ctx):

    global current_song

    voice = ctx.voice_client

    if voice is None:

        await ctx.send(
            "❌ DJ Pop ไม่ได้อยู่ในห้องพูดครับ"
        )

        return

    music_queue.clear()

    current_song = None

    if (
        voice.is_playing()
        or voice.is_paused()
    ):

        voice.stop()

    await ctx.send(
        "⏹️ หยุดเพลงและล้างคิวแล้วครับ"
    )


# ==================================================
# !leave
# ==================================================

@bot.command()
async def leave(ctx):

    global current_song

    if ctx.voice_client:

        music_queue.clear()

        current_song = None

        await ctx.voice_client.disconnect()

        await ctx.send(
            "👋 DJ Pop ออกจากห้องแล้วครับ"
        )

    else:

        await ctx.send(
            "❌ DJ Pop ไม่ได้อยู่ในห้องพูดครับ"
        )


# ==================================================
# Command Error
# ==================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        return

    if isinstance(
        error,
        commands.MissingRequiredArgument
    ):

        await ctx.send(
            "❌ ใช้คำสั่งไม่ครบครับ"
        )

        return

    print("=" * 60)

    print(
        "❌ COMMAND ERROR"
    )

    print(
        f"ประเภท: {type(error).__name__}"
    )

    print(
        f"รายละเอียด: {error}"
    )

    print("=" * 60)


# ==================================================
# Start
# ==================================================

print("=" * 60)

print("🚀 Starting DJ Pop...")

print("=" * 60)

bot.run(TOKEN)
