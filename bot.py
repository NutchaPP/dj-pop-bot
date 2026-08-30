import os
import asyncio
import shutil

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

FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"


# ============================================================
# MUSIC DATA
# ============================================================

queues = {}
current_song = {}
loop_mode = {}
music_locks = {}


# ============================================================
# COOKIE FILE
# ============================================================

COOKIE_CANDIDATES = [
    "/home/container/cookies.txt",
    "/home/container/youtube_cookie.txt",
    "cookies.txt",
    "youtube_cookie.txt",
]

COOKIE_FILE = None

for path in COOKIE_CANDIDATES:
    if os.path.isfile(path):
        COOKIE_FILE = path
        break


if COOKIE_FILE:
    print("🍪 Cookie file: FOUND")
    print(f"🍪 Cookie path: {COOKIE_FILE}")
else:
    print("⚠️ Cookie file: NOT FOUND")


# ============================================================
# YT-DLP OPTIONS
# ============================================================

YTDL_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,

    # ถ้าผู้ใช้พิมพ์ชื่อเพลง ให้ค้นหา YouTube
    "default_search": "ytsearch1",

    # ไม่ดาวน์โหลดลง disk
    "skip_download": True,

    # สำคัญ:
    # ไม่บังคับ ext=m4a
    # ให้ yt-dlp เลือก audio ที่มีจริง
    "format": "bestaudio/best",

    # ใช้ EJS
    "remote_components": ["ejs:npm"],

    # ไม่ใช้ playlist
    "extract_flat": False,
}


# ============================================================
# FFMPEG
# ============================================================

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    ),
    "options": "-vn",
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
        music_locks[guild_id] = asyncio.Lock()

    return music_locks[guild_id]


# ============================================================
# DURATION
# ============================================================

def format_duration(seconds):
    if not seconds:
        return "ไม่ทราบ"

    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "ไม่ทราบ"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


# ============================================================
# BUILD YTDLP OPTIONS
# ============================================================

def build_ytdl_options():
    options = YTDL_OPTIONS.copy()

    if COOKIE_FILE:
        options["cookiefile"] = COOKIE_FILE

    return options


# ============================================================
# EXTRACT SONG
# ============================================================

async def extract_song(query):

    loop = asyncio.get_running_loop()

    def extract():

        last_error = None

        # ====================================================
        # OPTION 1
        # ====================================================

        extraction_options = [
            {
                "format": "bestaudio/best",
            },
            {
                "format": "best",
            },
        ]

        for index, extra_options in enumerate(
            extraction_options,
            start=1
        ):

            try:

                print(
                    f"[YouTube] Extraction attempt {index}"
                )

                options = build_ytdl_options()

                options.update(
                    extra_options
                )

                with yt_dlp.YoutubeDL(
                    options
                ) as ytdl:

                    info = ytdl.extract_info(
                        query,
                        download=False
                    )

                    if not info:
                        continue

                    # ====================================================
                    # SEARCH RESULT
                    # ====================================================

                    if "entries" in info:

                        entries = info.get(
                            "entries"
                        )

                        if not entries:
                            continue

                        info = entries[0]

                    # ====================================================
                    # STREAM URL
                    # ====================================================

                    stream_url = info.get(
                        "url"
                    )

                    if not stream_url:

                        # บางกรณี yt-dlp ส่ง formats มา
                        # แต่ไม่มี url ระดับบนสุด
                        formats = info.get(
                            "formats",
                            []
                        )

                        audio_formats = [
                            fmt
                            for fmt in formats
                            if fmt.get("url")
                            and (
                                fmt.get("vcodec") == "none"
                                or fmt.get("acodec")
                                not in (None, "none")
                            )
                        ]

                        if audio_formats:

                            # เลือก format ที่มี audio
                            # และมี bitrate สูงสุดเท่าที่หาได้
                            audio_formats.sort(
                                key=lambda fmt: (
                                    fmt.get(
                                        "abr"
                                    ) or 0
                                ),
                                reverse=True
                            )

                            stream_url = (
                                audio_formats[0].get(
                                    "url"
                                )
                            )

                    if not stream_url:
                        continue

                    # ====================================================
                    # SONG DATA
                    # ====================================================

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
                    }

                    print(
                        "✅ [YouTube] Extraction successful"
                    )

                    print(
                        f"🎵 Title: {song['title']}"
                    )

                    return song

            except Exception as error:

                last_error = error

                print(
                    f"[YouTube] Extraction attempt "
                    f"{index} failed:"
                )

                print(
                    error
                )

                continue

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

        embed.set_thumbnail(
            url=song["thumbnail"]
        )

    try:

        await channel.send(
            embed=embed
        )

    except Exception as error:

        print(
            f"[MESSAGE ERROR] {error}"
        )


# ============================================================
# FIND TEXT CHANNEL
# ============================================================

def get_music_channel(guild):

    if guild.system_channel:
        return guild.system_channel

    me = guild.me

    if me is None:
        return None

    for channel in guild.text_channels:

        try:

            permissions = channel.permissions_for(
                me
            )

            if permissions.send_messages:

                return channel

        except Exception:
            continue

    return None


# ============================================================
# PLAY NEXT
# ============================================================

async def play_next(guild):

    guild_id = guild.id

    voice = guild.voice_client

    if voice is None:
        return

    # ========================================================
    # LOOP
    # ========================================================

    if (
        loop_mode.get(guild_id, False)
        and current_song.get(guild_id)
    ):

        song = current_song[guild_id]

    else:

        queue = get_queue(
            guild_id
        )

        if not queue:

            current_song.pop(
                guild_id,
                None
            )

            try:

                await voice.disconnect()

            except Exception:
                pass

            return

        song = queue.pop(0)

        current_song[guild_id] = song

    # ========================================================
    # FFMPEG
    # ========================================================

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

        await play_next(
            guild
        )

        return

    # ========================================================
    # CALLBACK
    # ========================================================

    def after_playing(error):

        if error:

            print(
                f"[PLAYER ERROR] {error}"
            )

        try:

            future = asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

        except Exception as callback_error:

            print(
                f"[CALLBACK ERROR] "
                f"{callback_error}"
            )

    # ========================================================
    # PLAY
    # ========================================================

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

        await play_next(
            guild
        )

        return

    # ========================================================
    # MESSAGE
    # ========================================================

    channel = get_music_channel(
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

            voice = await channel.connect()

        elif voice.channel != channel:

            await voice.move_to(
                channel
            )

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

    print("=" * 60)

    if COOKIE_FILE:

        print(
            f"🍪 Cookies: {COOKIE_FILE}"
        )

    else:

        print(
            "⚠️ Cookies: Not found"
        )

    print(
        f"FFmpeg   : {FFMPEG_PATH}"
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
async def join(ctx):

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

        if voice.is_playing():

            voice.stop()

    except Exception:
        pass

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

    voice = await ensure_voice(
        ctx
    )

    if voice is None:
        return

    guild_id = ctx.guild.id

    async with get_lock(
        guild_id
    ):

        loading = await ctx.send(
            "🔎 กำลังค้นหาเพลง..."
        )

        try:

            song = await extract_song(
                query
            )

        except Exception as error:

            print(
                "[YT-DLP ERROR]"
            )

            print(
                error
            )

            await loading.edit(
                content=(
                    "❌ ไม่สามารถดึงเพลงจาก YouTube "
                    "ได้ครับ\n\n"
                    "ลองเพลงอื่นอีกครั้งครับ"
                )
            )

            return

        if (
            song is None
            or not song.get("url")
        ):

            await loading.edit(
                content=(
                    "❌ ไม่พบเพลง หรือไม่พบ "
                    "Audio Stream ครับ"
                )
            )

            return

        queue = get_queue(
            guild_id
        )

        # ====================================================
        # CURRENTLY PLAYING
        # ====================================================

        if (
            voice.is_playing()
            or voice.is_paused()
        ):

            queue.append(
                song
            )

            await loading.edit(
                content=(
                    f"📋 เพิ่มเข้าคิวแล้วครับ\n\n"
                    f"🎵 **{song['title']}**\n"
                    f"📌 ลำดับที่ "
                    f"`{len(queue)}`"
                )
            )

            return

        # ====================================================
        # PLAY IMMEDIATELY
        # ====================================================

        current_song[
            guild_id
        ] = song

        try:

            await loading.delete()

        except Exception:
            pass

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

            await ctx.send(
                "❌ ไม่สามารถเปิด Audio ได้ครับ"
            )

            return

        # ====================================================
        # CALLBACK
        # ====================================================

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

        # ====================================================
        # PLAY
        # ====================================================

        try:

            voice.play(
                source,
                after=after_playing
            )

        except Exception as error:

            print(
                f"[PLAY ERROR] {error}"
            )

            await ctx.send(
                "❌ ไม่สามารถเล่นเพลงได้ครับ"
            )

            return

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

@bot.command(
    name="queue"
)
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

@bot.command(
    name="help"
)
async def help_command(ctx):

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

        await ctx.send(
            "❌ เกิดข้อผิดพลาดระหว่างทำงานครับ"
        )

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

    bot.run(TOKEN)
