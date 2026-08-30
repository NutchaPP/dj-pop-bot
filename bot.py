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

# Cookie อยู่โฟลเดอร์เดียวกับ bot.py
YOUTUBE_COOKIES = "/home/container/cookies.txt"


# ============================================================
# CHECK COOKIE FILE
# ============================================================

if os.path.isfile(YOUTUBE_COOKIES):
    print("🍪 Cookie file: FOUND")
    print(f"🍪 Cookie path: {YOUTUBE_COOKIES}")
else:
    print("❌ Cookie file: NOT FOUND")
    print(f"❌ Expected path: {YOUTUBE_COOKIES}")


# ============================================================
# MUSIC DATA
# ============================================================

queues = {}
current_song = {}
loop_mode = {}
music_locks = {}


# ============================================================
# YT-DLP BASE OPTIONS
# ============================================================

YTDL_BASE_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "default_search": "ytsearch",

    # EJS npm
    "remote_components": ["ejs:npm"],

    # ไม่ดาวน์โหลดไฟล์ลง disk
    "skip_download": True,

    # เลือก audio
    "format": (
        "bestaudio[ext=m4a]/"
        "bestaudio/"
        "best"
    ),

    # ป้องกันปัญหา certificate บาง hosting
    "nocheckcertificate": True,
}


# ============================================================
# YOUTUBE CLIENT FALLBACK
# ============================================================

YOUTUBE_CLIENTS = [
    ["android"],
    ["web"],
    ["mweb"],
    ["tv"],
]


# ============================================================
# FFMPEG OPTIONS
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
# FORMAT DURATION
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
# BUILD YT-DLP OPTIONS
# ============================================================

def build_ytdl_options(client):

    options = YTDL_BASE_OPTIONS.copy()

    options["extractor_args"] = {
        "youtube": {
            "player_client": client
        }
    }

    # ========================================================
    # COOKIE
    # ========================================================

    if os.path.isfile(YOUTUBE_COOKIES):

        options["cookiefile"] = YOUTUBE_COOKIES

        print(
            f"🍪 Using cookies: {YOUTUBE_COOKIES}"
        )

    else:

        print(
            "⚠️ Cookie file not found."
        )

    return options


# ============================================================
# EXTRACT SONG
# ============================================================

async def extract_song(query):

    loop = asyncio.get_running_loop()

    def extract():

        last_error = None

        for client in YOUTUBE_CLIENTS:

            try:

                print(
                    f"[YouTube] Trying client: {client}"
                )

                options = build_ytdl_options(
                    client
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

                    # Search result
                    if "entries" in info:

                        entries = info.get(
                            "entries"
                        )

                        if not entries:
                            continue

                        info = entries[0]

                    stream_url = info.get("url")

                    if not stream_url:
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
                    }

                    print(
                        "[YouTube] Extraction successful"
                    )

                    return song

            except Exception as error:

                last_error = error

                print(
                    f"[YouTube] Client {client} failed:"
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
# SEND NOW PLAYING EMBED
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
# PLAY NEXT
# ============================================================

async def play_next(guild):

    guild_id = guild.id

    voice = guild.voice_client

    if voice is None:
        return

    queue = get_queue(guild_id)

    # ========================================================
    # LOOP CURRENT SONG
    # ========================================================

    if (
        loop_mode.get(guild_id, False)
        and current_song.get(guild_id)
    ):

        song = current_song[guild_id]

    else:

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
    # CREATE FFMPEG SOURCE
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

        await play_next(guild)

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

            asyncio.run_coroutine_threadsafe(
                play_next(guild),
                bot.loop
            )

        except Exception as callback_error:

            print(
                "[CALLBACK ERROR]"
            )

            print(
                callback_error
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

        await play_next(guild)

        return

    # ========================================================
    # SEND MESSAGE
    # ========================================================

    channel = None

    if guild.system_channel:

        channel = guild.system_channel

    elif voice.channel:

        for text_channel in guild.text_channels:

            if text_channel.permissions_for(
                guild.me
            ).send_messages:

                channel = text_channel

                break

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
# BOT READY
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
            f"🎧 เข้าห้อง **{voice.channel.name}** แล้วครับ"
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
                    "ตรวจสอบ Cookie หรือส่ง Log "
                    "จาก Hosting มาให้ผมตรวจครับ"
                )
            )

            return

        if (
            song is None
            or not song.get("url")
        ):

            await loading.edit(
                content=(
                    "❌ ไม่พบเพลง หรือไม่สามารถ "
                    "ดึง Audio จาก YouTube ได้ครับ"
                )
            )

            return

        queue = get_queue(
            ctx.guild.id
        )

        # ====================================================
        # CURRENTLY PLAYING
        # ====================================================

        if (
            voice.is_playing()
            or voice.is_paused()
        ):

            queue.append(song)

            await loading.edit(
                content=(
                    f"📋 เพิ่มเข้าคิวแล้วครับ\n\n"
                    f"🎵 **{song['title']}**\n"
                    f"📌 ลำดับที่ `{len(queue)}`"
                )
            )

            return

        # ====================================================
        # PLAY IMMEDIATELY
        # ====================================================

        current_song[
            ctx.guild.id
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
