import os
import asyncio
import shutil
import subprocess

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp


# ==================================================
# โหลด Environment Variables
# ==================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError(
        "❌ ไม่พบ DISCORD_TOKEN ใน Environment Variables"
    )


# ==================================================
# Discord Intents
# ==================================================

intents = discord.Intents.default()
intents.message_content = True


# ==================================================
# สร้าง Bot
# ==================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==================================================
# Path
# ==================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


# ==================================================
# Cookies
# ==================================================

COOKIES_FILE = os.path.join(
    BASE_DIR,
    "cookies.txt"
)


# ==================================================
# yt-dlp OPTIONS
# ==================================================

YTDL_OPTIONS = {

    # ------------------------------------------------
    # Audio
    # ------------------------------------------------

    "format": "bestaudio/best",

    # ------------------------------------------------
    # ไม่เอา Playlist
    # ------------------------------------------------

    "noplaylist": True,

    # ------------------------------------------------
    # Output
    # ------------------------------------------------

    "quiet": True,

    "no_warnings": False,

    # ------------------------------------------------
    # Network
    # ------------------------------------------------

    "source_address": "0.0.0.0",

    "socket_timeout": 30,

    "retries": 5,

    "fragment_retries": 5,

    "file_access_retries": 3,

    "geo_bypass": True,

    "nocheckcertificate": True,

    # ------------------------------------------------
    # Search
    # ------------------------------------------------

    "default_search": "ytsearch1",

    # ------------------------------------------------
    # EJS
    #
    # ใช้ npm component
    # แต่ไม่บังคับ Runtime Deno
    # ------------------------------------------------

    "remote_components": [
        "ejs:npm"
    ],
}


# ==================================================
# Cookies
# ==================================================

if os.path.exists(COOKIES_FILE):

    YTDL_OPTIONS["cookiefile"] = COOKIES_FILE

    print("=" * 60)
    print("🍪 พบ cookies.txt")
    print(
        f"📁 {COOKIES_FILE}"
    )
    print("=" * 60)

else:

    print("=" * 60)
    print("⚠️ ไม่พบ cookies.txt")
    print("ℹ️ จะทำงานโดยไม่ใช้ Cookies")
    print("=" * 60)


# ==================================================
# ตรวจสอบ Runtime
# ==================================================

def print_runtime_status():

    print("=" * 60)
    print("🧩 JavaScript Runtime")
    print("=" * 60)

    # ------------------------------------------------
    # สำคัญ:
    # เราจะไม่บังคับใช้ /home/container/deno
    # เพราะ Log ก่อนหน้าพบ returncode -9
    # ------------------------------------------------

    deno = shutil.which("deno")
    node = shutil.which("node")
    bun = shutil.which("bun")

    if deno:

        print(
            f"🦕 พบ Deno: {deno}"
        )

    else:

        print(
            "⚠️ ไม่พบ Deno ใน PATH"
        )

    if node:

        print(
            f"🟢 พบ Node.js: {node}"
        )

    else:

        print(
            "⚠️ ไม่พบ Node.js ใน PATH"
        )

    if bun:

        print(
            f"🟠 พบ Bun: {bun}"
        )

    else:

        print(
            "⚠️ ไม่พบ Bun ใน PATH"
        )

    print()
    print(
        "ℹ️ Bot จะไม่กำหนด js_runtimes เอง"
    )

    print("=" * 60)


# ==================================================
# FFmpeg OPTIONS
# ==================================================

FFMPEG_OPTIONS = {

    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5 "
        "-nostdin"
    ),

    "options": (
        "-vn "
        "-loglevel warning"
    ),
}


# ==================================================
# Queue
# ==================================================

music_queue = []

current_song = None


# ==================================================
# yt-dlp Options Builder
# ==================================================

def build_ytdl_options():

    options = YTDL_OPTIONS.copy()

    if os.path.exists(COOKIES_FILE):

        options["cookiefile"] = COOKIES_FILE

    else:

        options.pop(
            "cookiefile",
            None
        )

    # ------------------------------------------------
    # สำคัญมาก
    #
    # ไม่ใส่:
    #
    # options["js_runtimes"]
    #
    # เพราะก่อนหน้านี้ Deno ถูก kill -9
    # ------------------------------------------------

    options.pop(
        "js_runtimes",
        None
    )

    return options


# ==================================================
# FFmpeg Check
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
# ตรวจสอบ yt-dlp Version
# ==================================================

def print_ytdlp_version():

    print("=" * 60)

    try:

        print(
            f"📦 yt-dlp version: "
            f"{yt_dlp.version.__version__}"
        )

    except Exception:

        print(
            "⚠️ ไม่สามารถอ่าน yt-dlp version"
        )

    print("=" * 60)


# ==================================================
# Extract YouTube
# ==================================================

def extract_youtube(
    url,
    format_value="bestaudio/best"
):

    options = build_ytdl_options()

    options["format"] = format_value

    print("=" * 60)

    print(
        "🎧 กำลัง Extract YouTube"
    )

    print(
        f"🔗 {url}"
    )

    print(
        f"🎛️ Format: {format_value}"
    )

    print("=" * 60)

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:

        info = ydl.extract_info(
            url,
            download=False
        )

        if not info:

            return None

        title = info.get(
            "title",
            "Unknown"
        )

        webpage_url = info.get(
            "webpage_url",
            url
        )

        audio_url = info.get(
            "url"
        )

        # ------------------------------------------------
        # กรณี info ไม่มี URL
        # ------------------------------------------------

        if not audio_url:

            formats = info.get(
                "formats",
                []
            )

            # ------------------------------------------------
            # เลือก Audio Only
            # ------------------------------------------------

            audio_formats = []

            for fmt in formats:

                fmt_url = fmt.get(
                    "url"
                )

                if not fmt_url:
                    continue

                acodec = fmt.get(
                    "acodec"
                )

                if (
                    acodec
                    and acodec != "none"
                ):

                    audio_formats.append(
                        fmt
                    )

            if audio_formats:

                audio_formats.sort(
                    key=lambda x: (
                        x.get(
                            "abr"
                        )
                        or 0
                    ),
                    reverse=True
                )

                audio_url = (
                    audio_formats[0]
                    .get("url")
                )

        if not audio_url:

            return None

        print("=" * 60)

        print(
            "✅ Extract สำเร็จ"
        )

        print(
            f"🎵 {title}"
        )

        print("=" * 60)

        return {
            "title": title,
            "url": audio_url,
            "webpage_url": webpage_url,
        }


# ==================================================
# ค้นหาเพลง
# ==================================================

async def search_song(
    search
):

    loop = asyncio.get_running_loop()

    def extract():

        print("=" * 60)

        print(
            f"🔎 กำลังค้นหา: {search}"
        )

        print("=" * 60)

        search_options = build_ytdl_options()

        # ------------------------------------------------
        # Search อย่างเดียวก่อน
        #
        # ไม่ใช้ format ตอน Search
        # ------------------------------------------------

        search_options.pop(
            "format",
            None
        )

        try:

            with yt_dlp.YoutubeDL(
                search_options
            ) as ydl:

                info = ydl.extract_info(
                    f"ytsearch1:{search}",
                    download=False
                )

        except Exception as e:

            print("=" * 60)

            print(
                "❌ SEARCH ERROR"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            print("=" * 60)

            raise

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

        webpage_url = (
            song.get("webpage_url")
            or song.get("original_url")
        )

        if not webpage_url:

            raise RuntimeError(
                "❌ Search ไม่พบ YouTube URL"
            )

        print(
            f"🎵 พบ: {title}"
        )

        print(
            f"🔗 {webpage_url}"
        )

        # ------------------------------------------------
        # Extract Audio
        # ------------------------------------------------

        result = None

        # ------------------------------------------------
        # Attempt 1
        # Best Audio
        # ------------------------------------------------

        try:

            result = extract_youtube(
                webpage_url,
                "bestaudio/best"
            )

        except Exception as e:

            print("=" * 60)

            print(
                "⚠️ Best Audio ล้มเหลว"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            print("=" * 60)

        if result:

            return result

        # ------------------------------------------------
        # Attempt 2
        # Format 18
        # ------------------------------------------------

        print(
            "🔄 กำลังลอง fallback format 18..."
        )

        try:

            result = extract_youtube(
                webpage_url,
                "18"
            )

        except Exception as e:

            print("=" * 60)

            print(
                "⚠️ Format 18 ล้มเหลว"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            print("=" * 60)

        if result:

            return result

        # ------------------------------------------------
        # Attempt 3
        # Best available
        # ------------------------------------------------

        print(
            "🔄 กำลังลอง fallback best..."
        )

        try:

            result = extract_youtube(
                webpage_url,
                "best"
            )

        except Exception as e:

            print("=" * 60)

            print(
                "⚠️ Best fallback ล้มเหลว"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            print("=" * 60)

        if result:

            return result

        raise RuntimeError(
            "ไม่สามารถดึง Audio URL จาก YouTube ได้"
        )

    # ------------------------------------------------
    # Retry
    # ------------------------------------------------

    last_error = None

    for attempt in range(
        1,
        4
    ):

        print(
            f"🔁 Extraction attempt "
            f"{attempt}/3"
        )

        try:

            return await loop.run_in_executor(
                None,
                extract
            )

        except Exception as e:

            last_error = e

            print("=" * 60)

            print(
                f"⚠️ Attempt {attempt} failed"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            print("=" * 60)

            if attempt < 3:

                await asyncio.sleep(
                    2
                )

    raise last_error


# ==================================================
# เล่นเพลงถัดไป
# ==================================================

async def play_next(
    ctx
):

    global current_song

    voice = ctx.voice_client

    if voice is None:

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

    print("=" * 60)

    print(
        f"▶️ กำลังเล่น: {title}"
    )

    print("=" * 60)

    try:

        ffmpeg_path = (
            shutil.which(
                "ffmpeg"
            )
            or "ffmpeg"
        )

        source = discord.FFmpegPCMAudio(
            audio_url,
            executable=ffmpeg_path,
            **FFMPEG_OPTIONS
        )

    except Exception as e:

        print("=" * 60)

        print(
            "❌ FFMPEG SOURCE ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print("=" * 60)

        current_song = None

        await ctx.send(
            "❌ เปิดเสียงเพลงไม่ได้ครับ\n"
            f"`{type(e).__name__}: {e}`"
        )

        return

    # ------------------------------------------------
    # Callback
    # ------------------------------------------------

    def after_playing(
        error
    ):

        if error:

            print(
                f"❌ Audio Error: {error}"
            )

        else:

            print(
                f"✅ เพลงจบ: {title}"
            )

        future = asyncio.run_coroutine_threadsafe(
            play_next(ctx),
            bot.loop
        )

        try:

            future.result(
                timeout=60
            )

        except Exception as e:

            print(
                "❌ PLAY NEXT ERROR:",
                e
            )

    try:

        voice.play(
            source,
            after=after_playing
        )

    except Exception as e:

        print("=" * 60)

        print(
            "❌ VOICE PLAY ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print("=" * 60)

        current_song = None

        await ctx.send(
            "❌ เล่นเพลงไม่ได้ครับ\n"
            f"`{type(e).__name__}: {e}`"
        )

        return

    await ctx.send(
        f"🎵 กำลังเล่น **{title}**"
    )


# ==================================================
# Bot Ready
# ==================================================

@bot.event
async def on_ready():

    print("=" * 60)

    print(
        f"✅ Login สำเร็จ: {bot.user}"
    )

    print(
        f"🆔 Bot ID: {bot.user.id}"
    )

    print("=" * 60)

    print(
        "📋 Commands:"
    )

    for command in bot.commands:

        print(
            f"   !{command.name}"
        )

    print("=" * 60)

    print_ytdlp_version()

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

        print(
            "❌ JOIN ERROR:",
            e
        )

        await ctx.send(
            "❌ Bot เข้าห้องไม่ได้ครับ\n"
            f"`{type(e).__name__}: {e}`"
        )


# ==================================================
# !play
# ==================================================

@bot.command()
async def play(
    ctx,
    *,
    search
):

    if ctx.author.voice is None:

        await ctx.send(
            "❌ ป๊อปต้องเข้าห้องพูดก่อนครับ"
        )

        return

    # ------------------------------------------------
    # Connect
    # ------------------------------------------------

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

    # ------------------------------------------------
    # Searching
    # ------------------------------------------------

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

        # ------------------------------------------------
        # Queue
        # ------------------------------------------------

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

        await play_next(
            ctx
        )

    except Exception as e:

        print("=" * 60)

        print(
            "❌ PLAY ERROR"
        )

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

    if len(text) > 1900:

        text = (
            text[:1900]
            + "\n..."
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

        try:

            if (
                ctx.voice_client.is_playing()
                or ctx.voice_client.is_paused()
            ):

                ctx.voice_client.stop()

        except Exception:

            pass

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
# Start Bot
# ==================================================

print("=" * 60)

print(
    "🚀 Starting DJ Pop..."
)

print("=" * 60)

bot.run(TOKEN)
