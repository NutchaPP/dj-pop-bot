import os
import asyncio
import shutil
import subprocess
import time

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
# Deno
# ==================================================

DENO_PATH = os.path.join(
    BASE_DIR,
    "deno"
)


# ==================================================
# ค้นหา JavaScript Runtime
# ==================================================

def find_runtime():

    # ------------------------------------------------
    # Deno
    # ------------------------------------------------

    if os.path.isfile(DENO_PATH):

        return "deno", DENO_PATH

    deno_path = shutil.which("deno")

    if deno_path:

        return "deno", deno_path

    deno_paths = [
        os.path.join(BASE_DIR, "bin", "deno"),
        "/home/container/deno",
        "/home/container/bin/deno",
        "/usr/local/bin/deno",
        "/usr/bin/deno",
        os.path.expanduser(
            "~/.deno/bin/deno"
        ),
    ]

    for path in deno_paths:

        if os.path.isfile(path):

            return "deno", path

    # ------------------------------------------------
    # Node.js
    # ------------------------------------------------

    node_path = shutil.which("node")

    if node_path:

        return "node", node_path

    node_paths = [
        os.path.join(BASE_DIR, "node"),
        os.path.join(BASE_DIR, "bin", "node"),
        "/usr/local/bin/node",
        "/usr/bin/node",
    ]

    for path in node_paths:

        if os.path.isfile(path):

            return "node", path

    # ------------------------------------------------
    # Bun
    # ------------------------------------------------

    bun_path = shutil.which("bun")

    if bun_path:

        return "bun", bun_path

    bun_paths = [
        os.path.join(BASE_DIR, "bun"),
        os.path.join(BASE_DIR, "bin", "bun"),
        "/usr/local/bin/bun",
        "/usr/bin/bun",
    ]

    for path in bun_paths:

        if os.path.isfile(path):

            return "bun", path

    return None, None


# ==================================================
# Runtime
# ==================================================

RUNTIME_NAME, RUNTIME_PATH = find_runtime()


# ==================================================
# Runtime Status
# ==================================================

def print_runtime_status():

    print("=" * 60)
    print("🧩 JavaScript Runtime")
    print("=" * 60)

    if not RUNTIME_PATH:

        print("❌ ไม่พบ JavaScript Runtime")
        print()
        print("⚠️ yt-dlp อาจไม่สามารถผ่าน")
        print("   YouTube EJS challenge ได้")
        print()
        print("Runtime ที่รองรับ:")
        print("   🦕 Deno")
        print("   🟢 Node.js")
        print("   🟠 Bun")
        print("=" * 60)

        return

    emoji = {
        "deno": "🦕",
        "node": "🟢",
        "bun": "🟠"
    }.get(
        RUNTIME_NAME,
        "🧩"
    )

    print(
        f"{emoji} พบ {RUNTIME_NAME.upper()}"
    )

    print(
        f"📁 Path: {RUNTIME_PATH}"
    )

    try:

        result = subprocess.run(
            [
                RUNTIME_PATH,
                "--version"
            ],
            capture_output=True,
            text=True,
            timeout=10
        )

        version = (
            result.stdout.strip()
            or result.stderr.strip()
        )

        if version:

            print(
                f"📦 Version:\n{version}"
            )

    except Exception as e:

        print(
            f"⚠️ ตรวจสอบ Runtime ไม่สำเร็จ: {e}"
        )

    print("=" * 60)


# ==================================================
# yt-dlp OPTIONS
# ==================================================

YTDL_OPTIONS = {

    # ------------------------------------------------
    # Audio
    # ------------------------------------------------

    "format": (
        "bestaudio/best"
    ),

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

    "geo_bypass": True,

    "nocheckcertificate": True,

    "socket_timeout": 30,

    "retries": 5,

    "fragment_retries": 5,

    "file_access_retries": 3,

    # ------------------------------------------------
    # Search
    # ------------------------------------------------

    "default_search": "ytsearch1",

    # ------------------------------------------------
    # Cookies
    # ------------------------------------------------

    "cookiefile": (
        COOKIES_FILE
        if os.path.exists(COOKIES_FILE)
        else None
    ),

    # ------------------------------------------------
    # EJS
    #
    # สำคัญ:
    # yt-dlp syntax ต้องเป็น list
    # ------------------------------------------------

    "remote_components": [
        "ejs:npm"
    ],

}


# ==================================================
# JavaScript Runtime
# ==================================================

if RUNTIME_PATH:

    YTDL_OPTIONS["js_runtimes"] = {
        RUNTIME_NAME: {
            "path": RUNTIME_PATH
        }
    }


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
# Lock
# ==================================================

play_lock = asyncio.Lock()


# ==================================================
# Cookies Status
# ==================================================

print("=" * 60)

if os.path.exists(COOKIES_FILE):

    print("🍪 พบ cookies.txt")

    print(
        f"📁 ตำแหน่ง: {COOKIES_FILE}"
    )

else:

    print("⚠️ ไม่พบ cookies.txt")

    print(
        f"📁 ตำแหน่งที่ต้องการ: {COOKIES_FILE}"
    )

print("=" * 60)


# ==================================================
# FFmpeg Check
# ==================================================

async def check_ffmpeg():

    loop = asyncio.get_running_loop()

    def run_check():

        return shutil.which(
            "ffmpeg"
        )

    try:

        ffmpeg_path = await loop.run_in_executor(
            None,
            run_check
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

    except Exception as e:

        print("=" * 60)

        print(
            "⚠️ ตรวจสอบ FFmpeg ไม่สำเร็จ"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print("=" * 60)


# ==================================================
# สร้าง yt-dlp Options
# ==================================================

def build_ytdl_options():

    options = YTDL_OPTIONS.copy()

    # ------------------------------------------------
    # ป้องกัน cookiefile เป็น None
    # ------------------------------------------------

    if not os.path.exists(
        COOKIES_FILE
    ):

        options.pop(
            "cookiefile",
            None
        )

    # ------------------------------------------------
    # Runtime
    # ------------------------------------------------

    if RUNTIME_PATH:

        options["js_runtimes"] = {
            RUNTIME_NAME: {
                "path": RUNTIME_PATH
            }
        }

    return options


# ==================================================
# ดึงข้อมูลเพลงจาก URL
# ==================================================

def extract_direct_audio(
    webpage_url
):

    print("=" * 60)

    print(
        "🎧 กำลังดึง Audio URL"
    )

    print(
        f"🔗 {webpage_url}"
    )

    print("=" * 60)

    options = build_ytdl_options()

    # ------------------------------------------------
    # พยายามครั้งที่ 1
    # Best Audio
    # ------------------------------------------------

    try:

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                webpage_url,
                download=False
            )

            if info:

                title = info.get(
                    "title",
                    "Unknown"
                )

                audio_url = info.get(
                    "url"
                )

                if audio_url:

                    print(
                        "✅ ได้ Audio URL"
                    )

                    return {
                        "title": title,
                        "url": audio_url,
                        "webpage_url": info.get(
                            "webpage_url",
                            webpage_url
                        )
                    }

                # ------------------------------------------------
                # บางครั้ง info ไม่มี url
                # ให้เลือกจาก formats
                # ------------------------------------------------

                formats = info.get(
                    "formats",
                    []
                )

                if formats:

                    audio_formats = [
                        f
                        for f in formats
                        if f.get("url")
                        and (
                            f.get("vcodec")
                            == "none"
                            or f.get("acodec")
                        )
                    ]

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

                        selected = (
                            audio_formats[0]
                        )

                        audio_url = selected.get(
                            "url"
                        )

                        if audio_url:

                            print(
                                "✅ ได้ Audio URL จาก formats"
                            )

                            return {
                                "title": title,
                                "url": audio_url,
                                "webpage_url": info.get(
                                    "webpage_url",
                                    webpage_url
                                )
                            }

    except Exception as e:

        print(
            "⚠️ Best Audio extraction failed"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

    # ------------------------------------------------
    # พยายามครั้งที่ 2
    # Format 18
    # ------------------------------------------------

    print(
        "🔄 กำลังลอง fallback format 18..."
    )

    fallback_options = build_ytdl_options()

    fallback_options["format"] = "18"

    try:

        with yt_dlp.YoutubeDL(
            fallback_options
        ) as ydl:

            info = ydl.extract_info(
                webpage_url,
                download=False
            )

            if info:

                audio_url = info.get(
                    "url"
                )

                title = info.get(
                    "title",
                    "Unknown"
                )

                if audio_url:

                    print(
                        "✅ Fallback format 18 สำเร็จ"
                    )

                    return {
                        "title": title,
                        "url": audio_url,
                        "webpage_url": info.get(
                            "webpage_url",
                            webpage_url
                        )
                    }

    except Exception as e:

        print(
            "⚠️ Format 18 failed"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

    return None


# ==================================================
# ค้นหาเพลง
# ==================================================

async def search_song(search):

    loop = asyncio.get_running_loop()

    def extract():

        print("=" * 60)

        print(
            f"🔎 กำลังค้นหา: {search}"
        )

        print("=" * 60)

        options = build_ytdl_options()

        # ------------------------------------------------
        # Search
        # ------------------------------------------------

        try:

            with yt_dlp.YoutubeDL(
                options
            ) as ydl:

                info = ydl.extract_info(
                    f"ytsearch1:{search}",
                    download=False
                )

        except Exception as e:

            print("=" * 60)

            print(
                "❌ SEARCH EXTRACTION ERROR"
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

        # ------------------------------------------------
        # ข้อมูลเพลง
        # ------------------------------------------------

        title = song.get(
            "title",
            search
        )

        webpage_url = song.get(
            "webpage_url"
        )

        # ------------------------------------------------
        # บางครั้ง search result
        # อาจคืน URL มา
        # ------------------------------------------------

        if not webpage_url:

            webpage_url = song.get(
                "original_url"
            )

        if not webpage_url:

            webpage_url = song.get(
                "url"
            )

        print(
            f"🎵 Search Result: {title}"
        )

        print(
            f"🔗 URL: {webpage_url}"
        )

        # ------------------------------------------------
        # สำคัญ:
        # อย่าพึ่งใช้ song["url"]
        # ------------------------------------------------

        if not webpage_url:

            raise RuntimeError(
                "ไม่พบ YouTube webpage URL"
            )

        # ------------------------------------------------
        # ดึง Direct Audio URL
        # ------------------------------------------------

        result = extract_direct_audio(
            webpage_url
        )

        if not result:

            raise RuntimeError(
                "ไม่สามารถดึง Audio URL จาก YouTube ได้"
            )

        print("=" * 60)

        print("✅ พบเพลง")

        print(
            f"🎵 {result['title']}"
        )

        print(
            f"🔗 {result['webpage_url']}"
        )

        print("=" * 60)

        return result

    # ------------------------------------------------
    # Retry
    # ------------------------------------------------

    last_error = None

    for attempt in range(
        1,
        4
    ):

        try:

            print(
                f"🔁 Extraction attempt "
                f"{attempt}/3"
            )

            return await loop.run_in_executor(
                None,
                extract
            )

        except Exception as e:

            last_error = e

            print(
                f"⚠️ Attempt {attempt} failed:"
            )

            print(
                f"{type(e).__name__}: {e}"
            )

            if attempt < 3:

                await asyncio.sleep(
                    2
                )

    print("=" * 60)

    print(
        "❌ SEARCH FAILED"
    )

    print(
        f"{type(last_error).__name__}: "
        f"{last_error}"
    )

    print("=" * 60)

    raise last_error


# ==================================================
# เล่นเพลงถัดไป
# ==================================================

async def play_next(ctx):

    global current_song

    async with play_lock:

        voice = ctx.voice_client

        if voice is None:

            return

        # ------------------------------------------------
        # Queue หมด
        # ------------------------------------------------

        if not music_queue:

            current_song = None

            try:

                await ctx.send(
                    "📭 เพลงในคิวหมดแล้วครับ"
                )

            except Exception:

                pass

            return

        # ------------------------------------------------
        # เอาเพลงออกจาก Queue
        # ------------------------------------------------

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

        # ------------------------------------------------
        # FFmpeg
        # ------------------------------------------------

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

            await ctx.send(
                "❌ เปิดเสียงเพลงไม่ได้ครับ\n"
                f"`{type(e).__name__}: {e}`"
            )

            current_song = None

            # ------------------------------------------------
            # ลองเพลงถัดไป
            # ------------------------------------------------

            if music_queue:

                await play_next(ctx)

            return

        # ------------------------------------------------
        # Callback
        # ------------------------------------------------

        def after_playing(error):

            if error:

                print("=" * 60)

                print(
                    "❌ Audio Error"
                )

                print(
                    f"{error}"
                )

                print("=" * 60)

            else:

                print(
                    f"✅ เพลงจบ: {title}"
                )

            # ------------------------------------------------
            # เรียกเพลงถัดไป
            # ------------------------------------------------

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
                    "❌ PLAY NEXT CALLBACK ERROR:",
                    callback_error
                )

        # ------------------------------------------------
        # Play
        # ------------------------------------------------

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

            await ctx.send(
                "❌ เล่นเพลงไม่ได้ครับ\n"
                f"`{type(e).__name__}: {e}`"
            )

            current_song = None

            return

    # ------------------------------------------------
    # ส่งข้อความนอก Lock
    # ------------------------------------------------

    try:

        await ctx.send(
            f"🎵 กำลังเล่น **{title}**"
        )

    except Exception:

        pass


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

    print(
        "📋 คำสั่งที่ Bot มี:"
    )

    for command in bot.commands:

        print(
            f"   !{command.name}"
        )

    print("=" * 60)

    if os.path.exists(
        COOKIES_FILE
    ):

        print(
            "🍪 Cookies: พร้อมใช้งาน"
        )

    else:

        print(
            "⚠️ Cookies: ไม่พบไฟล์"
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

        print(
            "❌ JOIN ERROR"
        )

        print(
            f"{type(e).__name__}: {e}"
        )

        print(
            f"{e}"
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
        # ถ้ามีเพลงเล่นอยู่
        # เพิ่ม Queue
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

        # ------------------------------------------------
        # Queue เพลง
        # ------------------------------------------------

        music_queue.append(
            song
        )

        try:

            await message.delete()

        except Exception:

            pass

        # ------------------------------------------------
        # Play
        # ------------------------------------------------

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

    # ------------------------------------------------
    # Discord message limit
    # ------------------------------------------------

    if len(text) > 1900:

        text = text[:1900] + "\n..."

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

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "❌ ป๊อปไม่มีสิทธิ์ใช้คำสั่งนี้ครับ"
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
print("🚀 Starting DJ Pop...")
print("=" * 60)

bot.run(TOKEN)
