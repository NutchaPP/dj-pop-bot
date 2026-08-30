import os
import asyncio
import shutil
import re
import subprocess
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
    raise ValueError(
        "ไม่พบ DISCORD_TOKEN ใน Environment Variables"
    )


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

FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

COOKIE_PATH = os.path.join(
    BASE_DIR,
    "cookies.txt"
)

DENO_PATH = os.path.join(
    BASE_DIR,
    "deno"
)

NODE_PATH = shutil.which("node")

if not NODE_PATH:
    possible_nodes = [
        "/usr/bin/node",
        "/usr/local/bin/node",
        "/home/container/node",
    ]

    for path in possible_nodes:
        if os.path.isfile(path):
            NODE_PATH = path
            break


# ============================================================
# COOKIE STATUS
# ============================================================

COOKIE_EXISTS = os.path.isfile(COOKIE_PATH)

if COOKIE_EXISTS:
    print("=" * 60)
    print("🍪 Cookie file: FOUND")
    print(f"🍪 Cookie path: {COOKIE_PATH}")
else:
    print("=" * 60)
    print("⚠️ Cookie file not found")


# ============================================================
# JAVASCRIPT RUNTIME
# ============================================================

JS_RUNTIME = None

if NODE_PATH:

    try:
        result = subprocess.run(
            [
                NODE_PATH,
                "--version"
            ],
            capture_output=True,
            text=True,
            timeout=5
        )

        node_version = result.stdout.strip()

        print(
            f"🟢 Node.js detected: {node_version}"
        )

        JS_RUNTIME = (
            f"node:{NODE_PATH}"
        )

    except Exception as error:

        print(
            f"⚠️ Node.js detected but unusable: {error}"
        )


if JS_RUNTIME is None:

    if os.path.isfile(DENO_PATH):

        try:

            os.chmod(
                DENO_PATH,
                0o755
            )

        except Exception:
            pass

        JS_RUNTIME = (
            f"deno:{DENO_PATH}"
        )

        print(
            f"🟡 Deno detected: {DENO_PATH}"
        )

    else:

        system_deno = shutil.which(
            "deno"
        )

        if system_deno:

            JS_RUNTIME = (
                f"deno:{system_deno}"
            )

            print(
                f"🟡 System Deno detected: {system_deno}"
            )


if JS_RUNTIME:

    print(
        f"⚙️ JS Runtime: {JS_RUNTIME}"
    )

else:

    print(
        "⚠️ No JavaScript runtime detected"
    )


print(
    f"🎧 FFmpeg: {FFMPEG_PATH}"
)

print("=" * 60)


# ============================================================
# MUSIC DATA
# ============================================================

queues = {}

current_song = {}

loop_mode = {}

music_locks = {}

play_generation = {}


# ============================================================
# YOUTUBE SETTINGS
# ============================================================

# ใช้ default client ของ yt-dlp เป็นหลัก
#
# web_embedded เป็น fallback ที่ไม่ต้อง login
# และไม่ควรบังคับ android เพราะ Android client
# ไม่ได้แก้ปัญหา Bot Check ได้ทุกกรณี
#
# yt-dlp ปัจจุบันมี EJS challenge system
# ซึ่งต้องใช้ JavaScript runtime
#
# หาก Node มีในเครื่อง -> ใช้ Node
# หากไม่มี -> ใช้ Deno
#
# อ้างอิงแนวทางปัจจุบันของ yt-dlp:
# EJS + supported JS runtime
#
# ============================================================

YOUTUBE_CLIENT_CONFIGS = [

    {
        "name": "default+web_embedded",
        "player_client": "default,web_embedded",
    },

    {
        "name": "web_embedded",
        "player_client": "web_embedded",
    },

    {
        "name": "android_vr",
        "player_client": "android_vr",
    },
]


# ============================================================
# BASE YT-DLP OPTIONS
# ============================================================

YTDL_BASE_OPTIONS = {

    "quiet": False,

    "no_warnings": False,

    "noplaylist": True,

    "default_search": "ytsearch",

    # เลือก audio ก่อน
    "format": (
        "bestaudio[ext=webm]/"
        "bestaudio[ext=m4a]/"
        "bestaudio/"
        "best"
    ),

    "socket_timeout": 30,

    "retries": 2,

    "fragment_retries": 2,

    "extractor_retries": 2,

    "file_access_retries": 2,

    "skip_unavailable_fragments": True,

    "nocheckcertificate": True,

    "extract_flat": False,

    # ไม่เก็บไฟล์ลง disk
    "cachedir": False,

    # ลดปัญหาเกี่ยวกับ encoding
    "encoding": "utf-8",

    # ไม่ download video
    "outtmpl": "-",
}


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
# DURATION
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

    return (
        f"ytsearch1:{query}"
    )


# ============================================================
# BUILD YT-DLP OPTIONS
# ============================================================

def build_ytdl_options(
    client_config,
    use_cookie
):

    options = YTDL_BASE_OPTIONS.copy()

    options["extractor_args"] = {

        "youtube": {

            "player_client": (
                client_config[
                    "player_client"
                ]
            )
        }
    }

    # --------------------------------------------------------
    # JAVASCRIPT RUNTIME
    # --------------------------------------------------------

    if JS_RUNTIME:

        options[
            "js_runtimes"
        ] = {

            JS_RUNTIME.split(":")[0]:
                JS_RUNTIME.split(":", 1)[1]
        }

    # --------------------------------------------------------
    # EJS
    # --------------------------------------------------------

    # yt-dlp[default] ติดตั้ง yt-dlp-ejs มาแล้ว
    #
    # ไม่เปิด remote npm โดยไม่จำเป็น
    # เพราะ Deno บน hosting ของป๊อปถูก kill -9
    #
    # --------------------------------------------------------

    # --------------------------------------------------------
    # COOKIE
    # --------------------------------------------------------

    if (
        use_cookie
        and COOKIE_EXISTS
    ):

        options[
            "cookiefile"
        ] = COOKIE_PATH

    return options


# ============================================================
# CHOOSE STREAM
# ============================================================

def choose_stream(info):

    if not info:
        return None

    # --------------------------------------------------------
    # Direct URL
    # --------------------------------------------------------

    direct_url = info.get(
        "url"
    )

    if direct_url:
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
    # Audio only
    # --------------------------------------------------------

    audio_formats = []

    for fmt in formats:

        url = fmt.get("url")

        if not url:
            continue

        acodec = fmt.get(
            "acodec"
        )

        if not acodec:
            continue

        if acodec == "none":
            continue

        audio_formats.append(
            fmt
        )

    if audio_formats:

        def score(fmt):

            abr = (
                fmt.get("abr")
                or 0
            )

            tbr = (
                fmt.get("tbr")
                or 0
            )

            return (
                float(abr),
                float(tbr)
            )

        audio_formats.sort(
            key=score,
            reverse=True
        )

        return (
            audio_formats[0]
            .get("url")
        )

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

            fmt.get("tbr")
            or 0,

            fmt.get("height")
            or 0
        ),

        reverse=True
    )

    return (
        valid_formats[0]
        .get("url")
    )


# ============================================================
# EXTRACT SONG
# ============================================================

async def extract_song(query):

    loop = (
        asyncio.get_running_loop()
    )

    def extract():

        search_query = (
            normalize_query(query)
        )

        last_error = None

        # ====================================================
        # COOKIE FIRST
        # ====================================================

        attempts = []

        if COOKIE_EXISTS:

            attempts.append(
                True
            )

        attempts.append(
            False
        )

        # ป้องกัน duplicate
        attempts = list(
            dict.fromkeys(attempts)
        )

        # ====================================================
        # CLIENTS
        # ====================================================

        for use_cookie in attempts:

            cookie_text = (
                "ON"
                if use_cookie
                else "OFF"
            )

            for client_config in (
                YOUTUBE_CLIENT_CONFIGS
            ):

                client_name = (
                    client_config["name"]
                )

                print(
                    "=" * 60
                )

                print(
                    "[YouTube] "
                    f"Client: {client_name}"
                )

                print(
                    "[YouTube] "
                    f"Cookie: {cookie_text}"
                )

                print(
                    "[YouTube] "
                    f"Extracting: {search_query}"
                )

                options = (
                    build_ytdl_options(
                        client_config,
                        use_cookie
                    )
                )

                try:

                    with yt_dlp.YoutubeDL(
                        options
                    ) as ytdl:

                        info = (
                            ytdl.extract_info(
                                search_query,
                                download=False
                            )
                        )

                    if not info:

                        print(
                            "[YouTube] "
                            "Empty result"
                        )

                        continue

                    # ------------------------------------------------
                    # SEARCH RESULT
                    # ------------------------------------------------

                    if "entries" in info:

                        entries = [

                            entry

                            for entry
                            in (
                                info.get(
                                    "entries",
                                    []
                                )
                                or []
                            )

                            if entry
                        ]

                        if not entries:

                            print(
                                "[YouTube] "
                                "No search result"
                            )

                            continue

                        info = entries[0]

                    # ------------------------------------------------
                    # STREAM
                    # ------------------------------------------------

                    stream_url = (
                        choose_stream(info)
                    )

                    if not stream_url:

                        print(
                            "[YouTube] "
                            "No playable audio stream"
                        )

                        continue

                    song = {

                        "title": (
                            info.get(
                                "title",
                                "Unknown Title"
                            )
                        ),

                        "url": stream_url,

                        "webpage_url": (
                            info.get(
                                "webpage_url",
                                query
                            )
                        ),

                        "duration": (
                            info.get(
                                "duration",
                                0
                            )
                        ),

                        "thumbnail": (
                            info.get(
                                "thumbnail"
                            )
                        ),

                        "uploader": (
                            info.get(
                                "uploader",
                                "Unknown"
                            )
                        ),
                    }

                    print(
                        "=" * 60
                    )

                    print(
                        "✅ [YouTube] "
                        "Extraction successful"
                    )

                    print(
                        f"🎵 Title: "
                        f"{song['title']}"
                    )

                    print(
                        f"⏱️ Duration: "
                        f"{format_duration(song['duration'])}"
                    )

                    print(
                        f"👤 Uploader: "
                        f"{song['uploader']}"
                    )

                    print(
                        "=" * 60
                    )

                    return song

                except Exception as error:

                    last_error = error

                    print(
                        "[YouTube] "
                        f"{client_name} failed:"
                    )

                    print(
                        error
                    )

                    error_text = str(
                        error
                    ).lower()

                    # ------------------------------------------------
                    # Cookie invalid
                    # ------------------------------------------------

                    if (
                        use_cookie
                        and (
                            "cookies are no longer valid"
                            in error_text
                            or
                            "cookie" in error_text
                            and "invalid"
                            in error_text
                        )
                    ):

                        print(
                            "⚠️ YouTube cookie "
                            "appears invalid."
                        )

                        # ไป no-cookie ต่อ
                        break

                    continue

        # ====================================================
        # ALL FAILED
        # ====================================================

        if last_error:

            raise last_error

        return None

    return await loop.run_in_executor(
        None,
        extract
    )


# ============================================================
# NOW PLAYING
# ============================================================

async def send_now_playing(
    channel,
    song
):

    embed = discord.Embed(

        title="🎵 กำลังเล่นเพลง",

        description=(
            f"**{song['title']}**\n\n"
            f"⏱️ "
            f"{format_duration(song['duration'])}\n"
            f"👤 "
            f"{song['uploader']}"
        )
    )

    if song.get(
        "webpage_url"
    ):

        embed.add_field(

            name="🔗 YouTube",

            value=song[
                "webpage_url"
            ],

            inline=False
        )

    if song.get(
        "thumbnail"
    ):

        embed.set_thumbnail(

            url=song[
                "thumbnail"
            ]
        )

    try:

        await channel.send(
            embed=embed
        )

    except Exception as error:

        print(
            "[MESSAGE ERROR]",
            error
        )


# ============================================================
# FIND TEXT CHANNEL
# ============================================================

def get_text_channel(
    guild
):

    if guild.system_channel:

        permissions = (
            guild.system_channel
            .permissions_for(
                guild.me
            )
        )

        if permissions.send_messages:

            return guild.system_channel

    for channel in guild.text_channels:

        permissions = (
            channel.permissions_for(
                guild.me
            )
        )

        if permissions.send_messages:

            return channel

    return None


# ============================================================
# PLAY NEXT
# ============================================================

async def play_next(
    guild
):

    guild_id = guild.id

    voice = (
        guild.voice_client
    )

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
        and current_song.get(
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

        song = queue.pop(
            0
        )

        current_song[
            guild_id
        ] = song

    # --------------------------------------------------------
    # SOURCE
    # --------------------------------------------------------

    try:

        source = (
            discord.FFmpegPCMAudio(

                song["url"],

                executable=(
                    FFMPEG_PATH
                ),

                **FFMPEG_OPTIONS
            )
        )

    except Exception as error:

        print(
            "[FFMPEG ERROR]",
            error
        )

        await play_next(
            guild
        )

        return

    # --------------------------------------------------------
    # GENERATION
    # --------------------------------------------------------

    generation = (
        play_generation.get(
            guild_id,
            0
        ) + 1
    )

    play_generation[
        guild_id
    ] = generation

    # --------------------------------------------------------
    # CALLBACK
    # --------------------------------------------------------

    def after_playing(error):

        if error:

            print(
                "[PLAYER ERROR]",
                error
            )

        async def continue_playing():

            try:

                await play_next(
                    guild
                )

            except Exception as callback_error:

                print(
                    "[CALLBACK ERROR]",
                    callback_error
                )

        try:

            asyncio.run_coroutine_threadsafe(
                continue_playing(),
                bot.loop
            )

        except Exception as callback_error:

            print(
                "[CALLBACK SCHEDULE ERROR]",
                callback_error
            )

    # --------------------------------------------------------
    # PLAY
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
            "[PLAY ERROR]",
            error
        )

        await play_next(
            guild
        )

        return

    # --------------------------------------------------------
    # MESSAGE
    # --------------------------------------------------------

    channel = get_text_channel(
        guild
    )

    if channel:

        await send_now_playing(
            channel,
            song
        )


# ============================================================
# ENSURE VOICE
# ============================================================

async def ensure_voice(
    ctx
):

    if ctx.author.voice is None:

        await ctx.send(
            "❌ ป๊อปต้องเข้าห้องเสียงก่อนครับ"
        )

        return None

    channel = (
        ctx.author.voice.channel
    )

    voice = (
        ctx.guild.voice_client
    )

    try:

        if voice is None:

            voice = await channel.connect(

                timeout=30,

                reconnect=True
            )

        elif voice.channel != channel:

            await voice.move_to(
                channel
            )

        return voice

    except Exception as error:

        print(
            "[VOICE ERROR]",
            error
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

    print(
        "🎵 DJ Pop Music Bot"
    )

    print("=" * 60)

    print(
        f"Bot      : {bot.user}"
    )

    print(
        f"Bot ID   : {bot.user.id}"
    )

    print(
        f"Servers  : {len(bot.guilds)}"
    )

    print(
        f"Python   : {os.sys.version}"
    )

    print(
        "🍪 Cookies: "
        + (
            COOKIE_PATH
            if COOKIE_EXISTS
            else "NOT FOUND"
        )
    )

    print(
        f"FFmpeg   : {FFMPEG_PATH}"
    )

    print(
        f"JS       : "
        f"{JS_RUNTIME or 'NOT FOUND'}"
    )

    print("=" * 60)

    print(
        "✅ Bot is online!"
    )

    print("=" * 60)


# ============================================================
# JOIN
# ============================================================

@bot.command()
async def join(
    ctx
):

    voice = await ensure_voice(
        ctx
    )

    if voice:

        await ctx.send(
            f"🎧 เข้าห้อง "
            f"**{voice.channel.name}** "
            f"แล้วครับ"
        )


# ============================================================
# LEAVE
# ============================================================

@bot.command()
async def leave(
    ctx
):

    voice = (
        ctx.guild.voice_client
    )

    if voice is None:

        await ctx.send(
            "❌ ตอนนี้บอทไม่ได้อยู่ในห้องเสียงครับ"
        )

        return

    guild_id = ctx.guild.id

    queues[
        guild_id
    ] = []

    current_song.pop(
        guild_id,
        None
    )

    loop_mode.pop(
        guild_id,
        None
    )

    play_generation.pop(
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

    # --------------------------------------------------------
    # VOICE
    # --------------------------------------------------------

    voice = await ensure_voice(
        ctx
    )

    if voice is None:
        return

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    async with get_lock(
        ctx.guild.id
    ):

        loading = await ctx.send(
            f"🔎 กำลังค้นหา "
            f"**{query}** ..."
        )

        try:

            song = await extract_song(
                query
            )

        except Exception as error:

            print(
                "=" * 60
            )

            print(
                "[YT-DLP ERROR]"
            )

            print(
                error
            )

            print(
                "=" * 60
            )

            try:

                await loading.edit(

                    content=(
                        "❌ YouTube "
                        "ไม่สามารถส่ง Audio "
                        "สำหรับเพลงนี้ได้ครับ\n\n"

                        "ปัญหาอยู่ที่ YouTube "
                        "EJS / Bot Check "
                        "ไม่ใช่ Discord Voice ครับ"
                    )
                )

            except Exception:
                pass

            return

        # ----------------------------------------------------
        # NO SONG
        # ----------------------------------------------------

        if (
            song is None
            or not song.get("url")
        ):

            try:

                await loading.edit(

                    content=(
                        "❌ ไม่พบ Audio "
                        "ที่สามารถเล่นได้ครับ"
                    )
                )

            except Exception:
                pass

            return

        queue = get_queue(
            ctx.guild.id
        )

        # ----------------------------------------------------
        # CURRENTLY PLAYING
        # ----------------------------------------------------

        if (
            voice.is_playing()
            or voice.is_paused()
        ):

            queue.append(
                song
            )

            await loading.edit(

                content=(

                    "📋 เพิ่มเข้าคิวแล้วครับ\n\n"

                    f"🎵 **{song['title']}**\n"

                    f"📌 ลำดับที่ "
                    f"`{len(queue)}`"
                )
            )

            return

        # ----------------------------------------------------
        # PLAY NOW
        # ----------------------------------------------------

        current_song[
            ctx.guild.id
        ] = song

        try:

            source = (
                discord.FFmpegPCMAudio(

                    song["url"],

                    executable=(
                        FFMPEG_PATH
                    ),

                    **FFMPEG_OPTIONS
                )
            )

        except Exception as error:

            print(
                "[FFMPEG ERROR]",
                error
            )

            await loading.edit(

                content=(
                    "❌ ไม่สามารถเปิด Audio ได้ครับ"
                )
            )

            return

        # ----------------------------------------------------
        # CALLBACK
        # ----------------------------------------------------

        def after_playing(error):

            if error:

                print(
                    "[PLAYER ERROR]",
                    error
                )

            async def next_song():

                try:

                    await play_next(
                        ctx.guild
                    )

                except Exception as next_error:

                    print(
                        "[CALLBACK ERROR]",
                        next_error
                    )

            try:

                asyncio.run_coroutine_threadsafe(

                    next_song(),

                    bot.loop
                )

            except Exception as callback_error:

                print(
                    "[CALLBACK SCHEDULE ERROR]",
                    callback_error
                )

        # ----------------------------------------------------
        # PLAY
        # ----------------------------------------------------

        try:

            voice.play(

                source,

                after=after_playing
            )

        except Exception as error:

            print(
                "[PLAY ERROR]",
                error
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
async def skip(
    ctx
):

    voice = (
        ctx.guild.voice_client
    )

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
async def pause(
    ctx
):

    voice = (
        ctx.guild.voice_client
    )

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
async def resume(
    ctx
):

    voice = (
        ctx.guild.voice_client
    )

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
async def stop(
    ctx
):

    voice = (
        ctx.guild.voice_client
    )

    if voice is None:

        await ctx.send(
            "❌ บอทยังไม่ได้อยู่ในห้องเสียงครับ"
        )

        return

    guild_id = ctx.guild.id

    queues[
        guild_id
    ] = []

    current_song.pop(
        guild_id,
        None
    )

    loop_mode.pop(
        guild_id,
        None
    )

    play_generation.pop(
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

@bot.command(
    name="queue"
)
async def show_queue(
    ctx
):

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

            value=current[
                "title"
            ],

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
async def loop(
    ctx
):

    guild_id = ctx.guild.id

    loop_mode[
        guild_id
    ] = not loop_mode.get(
        guild_id,
        False
    )

    if loop_mode[
        guild_id
    ]:

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
async def nowplaying(
    ctx
):

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

@bot.command(
    name="help"
)
async def help_command(
    ctx
):

    embed = discord.Embed(

        title="🎵 DJ Pop Music Bot",

        description=(
            "คำสั่งทั้งหมดของ DJ Pop"
        )
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

            "ใช้ `!help` "
            "เพื่อดูวิธีใช้"
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
                "❌ เกิดข้อผิดพลาดระหว่างทำงานครับ"
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
