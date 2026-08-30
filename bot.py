import os
import asyncio
import shutil
import re
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("ไม่พบ DISCORD_TOKEN ใน Environment Variables")


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)


# ============================================================
# DISCORD INTENTS
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True


# ============================================================
# BOT
# ============================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# ============================================================
# PATH
# ============================================================

BASE_DIR = "/home/container"

COOKIE_PATH = os.path.join(
    BASE_DIR,
    "cookies.txt"
)

DENO_PATH = os.path.join(
    BASE_DIR,
    "deno"
)

FFMPEG_PATH = (
    shutil.which("ffmpeg")
    or "/usr/bin/ffmpeg"
)


# ============================================================
# STARTUP CHECK
# ============================================================

print("=" * 60)

print("🍪 Cookie file:", "FOUND" if os.path.isfile(COOKIE_PATH) else "NOT FOUND")
if os.path.isfile(COOKIE_PATH):
    print(f"🍪 Cookie path: {COOKIE_PATH}")

if os.path.isfile(DENO_PATH):

    try:
        os.chmod(DENO_PATH, 0o755)
    except Exception:
        pass

    print(f"🟡 Deno detected: {DENO_PATH}")

else:

    print("⚠️ Deno: NOT FOUND")

print(f"🎧 FFmpeg: {FFMPEG_PATH}")

print("=" * 60)


# ============================================================
# MUSIC DATA
# ============================================================

queues = {}
current_song = {}
loop_mode = {}
music_locks = {}


# ============================================================
# YOUTUBE PROFILES
# ============================================================

# ใช้ default ก่อน
#
# ไม่บังคับ player_client แปลก ๆ
# เพราะ YouTube เปลี่ยนระบบบ่อย
#
# ถ้า cookie ใช้ไม่ได้ จะ fallback เป็น
# no-cookie profile
#
YOUTUBE_PROFILES = [

    {
        "name": "default_cookie",
        "cookie": True,
    },

    {
        "name": "default_no_cookie",
        "cookie": False,
    },

]


# ============================================================
# BASE YT-DLP OPTIONS
# ============================================================

YTDL_BASE_OPTIONS = {

    "quiet": False,

    "no_warnings": False,

    "noplaylist": True,

    "default_search": "ytsearch1",

    "format": "bestaudio/best",

    "socket_timeout": 20,

    "retries": 2,

    "fragment_retries": 2,

    "extractor_retries": 2,

    "file_access_retries": 2,

    "skip_unavailable_fragments": True,

    "nocheckcertificate": True,

    "extract_flat": False,

    "skip_download": True,

    "http_chunk_size": 10485760,

}


# ============================================================
# JS RUNTIME
# ============================================================

def build_js_runtime():

    if not os.path.isfile(DENO_PATH):
        return None

    return {
        "deno": {
            "path": DENO_PATH
        }
    }


# ============================================================
# BUILD YT-DLP OPTIONS
# ============================================================

def build_ytdl_options(profile):

    options = YTDL_BASE_OPTIONS.copy()

    use_cookie = profile.get(
        "cookie",
        False
    )

    # --------------------------------------------------------
    # Cookie
    # --------------------------------------------------------

    if (
        use_cookie
        and os.path.isfile(COOKIE_PATH)
    ):

        options["cookiefile"] = COOKIE_PATH

    # --------------------------------------------------------
    # Deno
    # --------------------------------------------------------

    js_runtime = build_js_runtime()

    if js_runtime:

        options["js_runtimes"] = js_runtime

    # ========================================================
    # สำคัญมาก
    #
    # ไม่ใช้:
    #
    # options["remote_components"] = ["ejs:github"]
    #
    # เพราะ requirements ใช้ yt-dlp[default]
    # ซึ่งติดตั้ง yt-dlp-ejs มาแล้ว
    #
    # ========================================================

    return options


# ============================================================
# FORMAT DURATION
# ============================================================

def format_duration(seconds):

    if not seconds:
        return "ไม่ทราบ"

    try:
        seconds = int(seconds)
    except (
        TypeError,
        ValueError
    ):
        return "ไม่ทราบ"

    hours = seconds // 3600

    minutes = (
        seconds % 3600
    ) // 60

    secs = seconds % 60

    if hours > 0:

        return (
            f"{hours}:"
            f"{minutes:02d}:"
            f"{secs:02d}"
        )

    return (
        f"{minutes}:"
        f"{secs:02d}"
    )


# ============================================================
# YOUTUBE URL
# ============================================================

def is_youtube_url(text):

    if not text:
        return False

    return bool(
        re.search(
            r"(youtube\.com|youtu\.be)",
            text,
            re.IGNORECASE
        )
    )


# ============================================================
# NORMALIZE QUERY
# ============================================================

def normalize_query(query):

    query = query.strip()

    if is_youtube_url(query):
        return query

    return f"ytsearch1:{query}"


# ============================================================
# ERROR CHECK
# ============================================================

def is_bot_check_error(error):

    text = str(error).lower()

    keywords = [

        "sign in to confirm",

        "you're not a bot",

        "you’re not a bot",

        "confirm you're not a bot",

        "confirm you’re not a bot",

    ]

    return any(
        keyword in text
        for keyword in keywords
    )


# ============================================================
# CHOOSE AUDIO STREAM
# ============================================================

def choose_stream(info):

    if not info:
        return None

    # --------------------------------------------------------
    # Direct URL
    # --------------------------------------------------------

    direct_url = info.get("url")

    if direct_url:

        acodec = info.get("acodec")

        if (
            acodec
            and acodec != "none"
        ):

            return direct_url

    # --------------------------------------------------------
    # Formats
    # --------------------------------------------------------

    formats = (
        info.get("formats")
        or []
    )

    if not formats:
        return None

    # --------------------------------------------------------
    # Audio formats
    # --------------------------------------------------------

    audio_formats = []

    for fmt in formats:

        url = fmt.get("url")

        if not url:
            continue

        acodec = fmt.get("acodec")

        if not acodec:
            continue

        if acodec == "none":
            continue

        audio_formats.append(fmt)

    # --------------------------------------------------------
    # Best audio
    # --------------------------------------------------------

    if audio_formats:

        def score(fmt):

            abr = fmt.get("abr") or 0
            tbr = fmt.get("tbr") or 0
            asr = fmt.get("asr") or 0

            try:
                abr = float(abr)
            except Exception:
                abr = 0

            try:
                tbr = float(tbr)
            except Exception:
                tbr = 0

            try:
                asr = float(asr)
            except Exception:
                asr = 0

            return (
                abr,
                tbr,
                asr
            )

        audio_formats.sort(
            key=score,
            reverse=True
        )

        return audio_formats[0].get("url")

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    valid_formats = [
        fmt
        for fmt in formats
        if fmt.get("url")
    ]

    if not valid_formats:
        return None

    valid_formats.sort(
        key=lambda fmt: (
            fmt.get("tbr") or 0,
            fmt.get("height") or 0
        ),
        reverse=True
    )

    return valid_formats[0].get("url")


# ============================================================
# EXTRACT SONG
# ============================================================

async def extract_song(query):

    loop = asyncio.get_running_loop()

    def extract():

        search_query = normalize_query(query)

        last_error = None

        for profile in YOUTUBE_PROFILES:

            profile_name = profile["name"]

            use_cookie = profile.get(
                "cookie",
                False
            )

            print("=" * 60)

            print(
                f"[YouTube] Profile: {profile_name}"
            )

            print(
                "[YouTube] Cookie: "
                f"{'ON' if use_cookie else 'OFF'}"
            )

            if os.path.isfile(DENO_PATH):

                print(
                    f"[YouTube] JS: deno:{DENO_PATH}"
                )

            print(
                f"[YouTube] Extracting: {search_query}"
            )

            options = build_ytdl_options(
                profile
            )

            try:

                with yt_dlp.YoutubeDL(
                    options
                ) as ytdl:

                    info = ytdl.extract_info(
                        search_query,
                        download=False
                    )

                    if not info:

                        print(
                            "[YouTube] Empty result"
                        )

                        continue

                    # ------------------------------------------------
                    # Search result
                    # ------------------------------------------------

                    if "entries" in info:

                        entries = [
                            entry
                            for entry in info.get(
                                "entries",
                                []
                            )
                            if entry
                        ]

                        if not entries:

                            print(
                                "[YouTube] No search result"
                            )

                            continue

                        info = entries[0]

                    # ------------------------------------------------
                    # Audio
                    # ------------------------------------------------

                    stream_url = choose_stream(
                        info
                    )

                    if not stream_url:

                        print(
                            "[YouTube] "
                            "No playable audio"
                        )

                        continue

                    song = {

                        "title": info.get(
                            "title",
                            "Unknown Title"
                        ),

                        "url": stream_url,

                        "webpage_url": info.get(
                            "webpage_url",
                            query
                        ),

                        "duration": info.get(
                            "duration",
                            0
                        ),

                        "thumbnail": info.get(
                            "thumbnail"
                        ),

                        "uploader": info.get(
                            "uploader",
                            "Unknown"
                        ),

                        "id": info.get(
                            "id"
                        ),

                    }

                    print("=" * 60)

                    print(
                        "[YouTube] Extraction SUCCESS"
                    )

                    print(
                        f"[YouTube] Title: "
                        f"{song['title']}"
                    )

                    print(
                        f"[YouTube] Duration: "
                        f"{format_duration(song['duration'])}"
                    )

                    print("=" * 60)

                    return song

            except Exception as error:

                last_error = error

                print("=" * 60)

                print(
                    f"[YouTube] "
                    f"{profile_name} failed:"
                )

                print(error)

                print("=" * 60)

                # ------------------------------------------------
                # Cookie invalid
                # ------------------------------------------------

                if (
                    "cookies are no longer valid"
                    in str(error).lower()
                    or
                    "cookie" in str(error).lower()
                    and
                    "rotated" in str(error).lower()
                ):

                    print(
                        "[YouTube] ⚠️ "
                        "Cookie may be expired."
                    )

                # ------------------------------------------------
                # Bot check
                # ------------------------------------------------

                if is_bot_check_error(error):

                    print(
                        "[YouTube] ⚠️ "
                        "YouTube bot check detected."
                    )

                # ------------------------------------------------
                # Deno killed
                # ------------------------------------------------

                if (
                    "returncode: -9"
                    in str(error)
                    or
                    (
                        "process"
                        in str(error).lower()
                        and
                        "-9"
                        in str(error)
                    )
                ):

                    print(
                        "[YouTube] ⚠️ "
                        "Deno was killed by hosting."
                    )

                continue

        # --------------------------------------------------------
        # ALL FAILED
        # --------------------------------------------------------

        print("=" * 60)

        print(
            "[YouTube] ALL extraction profiles failed"
        )

        print("=" * 60)

        if last_error:
            raise last_error

        return None

    return await loop.run_in_executor(
        None,
        extract
    )


# ============================================================
# SEND NOW PLAYING
# ============================================================

async def send_now_playing(
    channel,
    song
):

    embed = discord.Embed(
        title="🎵 กำลังเล่นเพลง",
        description=(
            f"**{song['title']}**\n\n"
            f"⏱️ {format_duration(song['duration'])}\n"
            f"👤 {song['uploader']}"
        )
    )

    if song.get("webpage_url"):

        embed.add_field(
            name="🔗 YouTube",
            value=song["webpage_url"],
            inline=False
        )

    if song.get("thumbnail"):

        try:

            embed.set_thumbnail(
                url=song["thumbnail"]
            )

        except Exception:
            pass

    try:

        await channel.send(
            embed=embed
        )

    except Exception as error:

        print(
            f"[MESSAGE ERROR] {error}"
        )


# ============================================================
# QUEUE
# ============================================================

def get_queue(guild_id):

    if guild_id not in queues:
        queues[guild_id] = []

    return queues[guild_id]


# ============================================================
# LOCK
# ============================================================

def get_lock(guild_id):

    if guild_id not in music_locks:

        music_locks[guild_id] = (
            asyncio.Lock()
        )

    return music_locks[guild_id]


# ============================================================
# FFMPEG
# ============================================================

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


# ============================================================
# PLAY NEXT
# ============================================================

async def play_next(guild):

    guild_id = guild.id

    voice = guild.voice_client

    if voice is None:
        return

    queue = get_queue(
        guild_id
    )

    # --------------------------------------------------------
    # LOOP
    # --------------------------------------------------------

    if (
        loop_mode.get(
            guild_id,
            False
        )
        and
        current_song.get(
            guild_id
        )
    ):

        song = current_song[
            guild_id
        ]

    else:

        if not queue:

            current_song.pop(
                guild_id,
                None
            )

            return

        song = queue.pop(0)

        current_song[
            guild_id
        ] = song

    # --------------------------------------------------------
    # Source
    # --------------------------------------------------------

    try:

        source = discord.FFmpegPCMAudio(
            song["url"],
            executable=FFMPEG_PATH,
            **FFMPEG_OPTIONS
        )

    except Exception as error:

        print(
            f"[FFMPEG ERROR] {error}"
        )

        await play_next(guild)

        return

    # --------------------------------------------------------
    # Callback
    # --------------------------------------------------------

    def after_playing(error):

        if error:

            print(
                f"[PLAYER ERROR] {error}"
            )

        try:

            asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

        except Exception as callback_error:

            print(
                f"[CALLBACK ERROR] "
                f"{callback_error}"
            )

    # --------------------------------------------------------
    # Play
    # --------------------------------------------------------

    try:

        if voice.is_playing():
            voice.stop()

        voice.play(
            source,
            after=after_playing
        )

    except Exception as error:

        print(
            f"[PLAY ERROR] {error}"
        )

        await play_next(guild)

        return

    # --------------------------------------------------------
    # Find channel
    # --------------------------------------------------------

    channel = None

    if guild.system_channel:

        try:

            permissions = (
                guild.system_channel
                .permissions_for(
                    guild.me
                )
            )

            if permissions.send_messages:

                channel = guild.system_channel

        except Exception:
            pass

    if channel is None:

        for text_channel in guild.text_channels:

            try:

                permissions = (
                    text_channel
                    .permissions_for(
                        guild.me
                    )
                )

                if permissions.send_messages:

                    channel = text_channel

                    break

            except Exception:
                continue

    if channel:

        await send_now_playing(
            channel,
            song
        )


# ============================================================
# ENSURE VOICE
# ============================================================

async def ensure_voice(ctx):

    if ctx.author.voice is None:

        await ctx.send(
            "❌ ป๊อปต้องเข้าห้องเสียงก่อนครับ"
        )

        return None

    channel = ctx.author.voice.channel

    voice = ctx.guild.voice_client

    try:

        if voice is None:

            voice = await channel.connect(
                timeout=30,
                reconnect=True
            )

        elif voice.channel != channel:

            await voice.move_to(channel)

        return voice

    except Exception as error:

        print(
            f"[VOICE ERROR] {error}"
        )

        await ctx.send(
            "❌ ไม่สามารถเข้าห้องเสียงได้ครับ"
        )

        return None


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    print("=" * 60)

    print("🎵 DJ Pop Music Bot")

    print("=" * 60)

    print(f"Bot      : {bot.user}")
    print(f"Bot ID   : {bot.user.id}")
    print(f"Servers  : {len(bot.guilds)}")
    print(f"Python   : {os.sys.version}")
    print(f"🍪 Cookies: {COOKIE_PATH}")
    print(f"FFmpeg   : {FFMPEG_PATH}")

    if os.path.isfile(DENO_PATH):

        print(
            f"JS       : deno:{DENO_PATH}"
        )

    else:

        print(
            "JS       : NOT FOUND"
        )

    print("=" * 60)

    print("✅ Bot is online!")

    print("=" * 60)


# ============================================================
# JOIN
# ============================================================

@bot.command()
async def join(ctx):

    voice = await ensure_voice(ctx)

    if voice:

        await ctx.send(
            f"🎧 เข้าห้อง "
            f"**{voice.channel.name}** แล้วครับ"
        )


# ============================================================
# LEAVE
# ============================================================

@bot.command()
async def leave(ctx):

    voice = ctx.guild.voice_client

    if voice is None:

        await ctx.send(
            "❌ ตอนนี้บอทไม่ได้อยู่ในห้องเสียงครับ"
        )

        return

    guild_id = ctx.guild.id

    queues[guild_id] = []

    current_song.pop(
        guild_id,
        None
    )

    loop_mode.pop(
        guild_id,
        None
    )

    try:

        await voice.disconnect()

    except Exception:
        pass

    await ctx.send(
        "👋 ออกจากห้องเสียงแล้วครับ"
    )


# ============================================================
# PLAY
# ============================================================

@bot.command()
async def play(
    ctx,
    *,
    query=None
):

    if not query:

        await ctx.send(
            "❌ ใช้แบบนี้ครับ\n\n"
            "`!play ชื่อเพลง`\n"
            "หรือ\n"
            "`!play https://youtube.com/...`"
        )

        return

    voice = await ensure_voice(ctx)

    if voice is None:
        return

    async with get_lock(
        ctx.guild.id
    ):

        loading = await ctx.send(
            f"🔎 กำลังค้นหา **{query}** ..."
        )

        try:

            song = await extract_song(
                query
            )

        except Exception as error:

            print("=" * 60)
            print("[YT-DLP ERROR]")
            print(error)
            print("=" * 60)

            try:

                await loading.edit(
                    content=(
                        "❌ YouTube ไม่สามารถส่ง "
                        "Audio stream ให้บอทได้ครับ\n\n"
                        "ถ้ายังเป็นเหมือนเดิม "
                        "ให้เช็ก `requirements.txt` "
                        "และ Deno ครับ"
                    )
                )

            except Exception:
                pass

            return

        if (
            song is None
            or not song.get("url")
        ):

            await loading.edit(
                content=(
                    "❌ ไม่พบ Audio "
                    "ที่สามารถเล่นได้ครับ"
                )
            )

            return

        queue = get_queue(
            ctx.guild.id
        )

        # ----------------------------------------------------
        # Queue
        # ----------------------------------------------------

        if (
            voice.is_playing()
            or voice.is_paused()
        ):

            queue.append(song)

            await loading.edit(
                content=(
                    "📋 เพิ่มเข้าคิวแล้วครับ\n\n"
                    f"🎵 **{song['title']}**\n"
                    f"📌 ลำดับที่ `{len(queue)}`"
                )
            )

            return

        # ----------------------------------------------------
        # Current
        # ----------------------------------------------------

        current_song[
            ctx.guild.id
        ] = song

        try:

            source = discord.FFmpegPCMAudio(
                song["url"],
                executable=FFMPEG_PATH,
                **FFMPEG_OPTIONS
            )

        except Exception as error:

            print(
                f"[FFMPEG ERROR] {error}"
            )

            await loading.edit(
                content=(
                    "❌ ไม่สามารถเปิด Audio ได้ครับ"
                )
            )

            return

        # ----------------------------------------------------
        # Callback
        # ----------------------------------------------------

        def after_playing(error):

            if error:

                print(
                    f"[PLAYER ERROR] {error}"
                )

            try:

                asyncio.run_coroutine_threadsafe(
                    play_next(ctx.guild),
                    bot.loop
                )

            except Exception as callback_error:

                print(
                    f"[CALLBACK ERROR] "
                    f"{callback_error}"
                )

        # ----------------------------------------------------
        # Play
        # ----------------------------------------------------

        try:

            voice.play(
                source,
                after=after_playing
            )

        except Exception as error:

            print(
                f"[PLAY ERROR] {error}"
            )

            await loading.edit(
                content=(
                    "❌ ไม่สามารถเล่นเพลงได้ครับ"
                )
            )

            return

        try:

            await loading.delete()

        except Exception:
            pass

        await send_now_playing(
            ctx.channel,
            song
        )


# ============================================================
# SKIP
# ============================================================

@bot.command()
async def skip(ctx):

    voice = ctx.guild.voice_client

    if voice is None:

        await ctx.send(
            "❌ บอทยังไม่ได้อยู่ในห้องเสียงครับ"
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


# ============================================================
# PAUSE
# ============================================================

@bot.command()
async def pause(ctx):

    voice = ctx.guild.voice_client

    if voice is None:

        await ctx.send(
            "❌ บอทยังไม่ได้อยู่ในห้องเสียงครับ"
        )

        return

    if not voice.is_playing():

        await ctx.send(
            "❌ ตอนนี้ไม่มีเพลงกำลังเล่นครับ"
        )

        return

    voice.pause()

    await ctx.send(
        "⏸️ หยุดเพลงชั่วคราวแล้วครับ"
    )


# ============================================================
# RESUME
# ============================================================

@bot.command()
async def resume(ctx):

    voice = ctx.guild.voice_client

    if voice is None:

        await ctx.send(
            "❌ บอทยังไม่ได้อยู่ในห้องเสียงครับ"
        )

        return

    if not voice.is_paused():

        await ctx.send(
            "❌ เพลงไม่ได้ถูกพักไว้ครับ"
        )

        return

    voice.resume()

    await ctx.send(
        "▶️ เล่นเพลงต่อแล้วครับ"
    )


# ============================================================
# STOP
# ============================================================

@bot.command()
async def stop(ctx):

    voice = ctx.guild.voice_client

    if voice is None:

        await ctx.send(
            "❌ บอทยังไม่ได้อยู่ในห้องเสียงครับ"
        )

        return

    guild_id = ctx.guild.id

    queues[guild_id] = []

    current_song.pop(
        guild_id,
        None
    )

    loop_mode.pop(
        guild_id,
        None
    )

    if (
        voice.is_playing()
        or voice.is_paused()
    ):

        voice.stop()

    await ctx.send(
        "⏹️ หยุดเพลงและล้างคิวแล้วครับ"
    )


# ============================================================
# QUEUE
# ============================================================

@bot.command(name="queue")
async def show_queue(ctx):

    queue = get_queue(
        ctx.guild.id
    )

    current = current_song.get(
        ctx.guild.id
    )

    if (
        current is None
        and not queue
    ):

        await ctx.send(
            "📭 ตอนนี้คิวว่างครับ"
        )

        return

    embed = discord.Embed(
        title="🎵 DJ Pop Queue"
    )

    if current:

        embed.add_field(
            name="▶️ กำลังเล่น",
            value=current["title"],
            inline=False
        )

    if queue:

        text = ""

        for index, song in enumerate(
            queue[:10],
            start=1
        ):

            text += (
                f"`{index}.` "
                f"{song['title']}\n"
            )

        if len(queue) > 10:

            text += (
                f"\n... และอีก "
                f"{len(queue) - 10} เพลง"
            )

        embed.add_field(
            name="📋 คิวเพลง",
            value=text,
            inline=False
        )

    await ctx.send(
        embed=embed
    )


# ============================================================
# LOOP
# ============================================================

@bot.command()
async def loop(ctx):

    guild_id = ctx.guild.id

    loop_mode[guild_id] = not loop_mode.get(
        guild_id,
        False
    )

    if loop_mode[guild_id]:

        await ctx.send(
            "🔁 เปิด Loop เพลงปัจจุบันแล้วครับ"
        )

    else:

        await ctx.send(
            "➡️ ปิด Loop แล้วครับ"
        )


# ============================================================
# NOW PLAYING
# ============================================================

@bot.command()
async def nowplaying(ctx):

    song = current_song.get(
        ctx.guild.id
    )

    if song is None:

        await ctx.send(
            "❌ ตอนนี้ไม่มีเพลงกำลังเล่นครับ"
        )

        return

    await send_now_playing(
        ctx.channel,
        song
    )


# ============================================================
# HELP
# ============================================================

@bot.command(name="help")
async def help_command(ctx):

    embed = discord.Embed(
        title="🎵 DJ Pop Music Bot",
        description="คำสั่งทั้งหมดของ DJ Pop"
    )

    embed.add_field(
        name="🎧 Music",
        value=(
            "`!play <เพลง>` - เล่นเพลง\n"
            "`!skip` - ข้ามเพลง\n"
            "`!pause` - พักเพลง\n"
            "`!resume` - เล่นต่อ\n"
            "`!stop` - หยุดและล้างคิว\n"
            "`!queue` - ดูคิว\n"
            "`!nowplaying` - เพลงปัจจุบัน\n"
            "`!loop` - เปิด/ปิด Loop"
        ),
        inline=False
    )

    embed.add_field(
        name="🔊 Voice",
        value=(
            "`!join` - เข้าห้องเสียง\n"
            "`!leave` - ออกจากห้องเสียง"
        ),
        inline=False
    )

    await ctx.send(
        embed=embed
    )


# ============================================================
# COMMAND ERROR
# ============================================================

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
            "❌ ข้อมูลไม่ครบครับ\n"
            "ใช้ `!help` เพื่อดูวิธีใช้"
        )

        return

    if isinstance(
        error,
        commands.CommandInvokeError
    ):

        print(
            "[COMMAND ERROR]"
        )

        print(
            error.original
        )

        try:

            await ctx.send(
                "❌ เกิดข้อผิดพลาด "
                "ระหว่างทำงานครับ"
            )

        except Exception:
            pass

        return

    print(
        f"[ERROR] {error}"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print(
        "🚀 Starting DJ Pop Bot..."
    )

    bot.run(
        TOKEN
    )
