import os
import asyncio
import shutil
import subprocess

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp


# ==================================================
# LOAD ENVIRONMENT VARIABLES
# ==================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError(
        "ไม่พบ DISCORD_TOKEN ใน Environment Variables"
    )


# ==================================================
# DISCORD INTENTS
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True


# ==================================================
# BOT
# ==================================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None
)


# ==================================================
# MUSIC SETTINGS
# ==================================================

FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"

YTDL_FORMAT = (
    "bestaudio[ext=m4a]/"
    "bestaudio/best"
)

YTDL_OPTIONS = {
    "format": YTDL_FORMAT,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "noplaylist": True,

    # สำคัญสำหรับ YouTube เวอร์ชันใหม่
    "remote_components": ["ejs:npm"],

    "extractor_args": {
        "youtube": {
            "player_client": [
                "android",
                "web"
            ]
        }
    },
}

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 "
        "-reconnect_streamed 1 "
        "-reconnect_delay_max 5"
    ),
    "options": "-vn",
}


# ==================================================
# SERVER MUSIC DATA
# ==================================================

queues = {}
current_song = {}
loop_mode = {}
music_locks = {}


# ==================================================
# GET QUEUE
# ==================================================

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = []

    return queues[guild_id]


# ==================================================
# GET LOCK
# ==================================================

def get_lock(guild_id):
    if guild_id not in music_locks:
        music_locks[guild_id] = asyncio.Lock()

    return music_locks[guild_id]


# ==================================================
# YOUTUBE EXTRACT
# ==================================================

async def extract_song(query):
    loop = asyncio.get_running_loop()

    def extract():
        options = YTDL_OPTIONS.copy()

        with yt_dlp.YoutubeDL(options) as ytdl:
            info = ytdl.extract_info(
                query,
                download=False
            )

            if "entries" in info:
                entries = info.get("entries")

                if not entries:
                    return None

                info = entries[0]

            return {
                "title": info.get(
                    "title",
                    "Unknown Title"
                ),
                "url": info.get("url"),
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

    return await loop.run_in_executor(
        None,
        extract
    )


# ==================================================
# FORMAT DURATION
# ==================================================

def format_duration(seconds):
    if not seconds:
        return "ไม่ทราบ"

    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


# ==================================================
# PLAY NEXT
# ==================================================

async def play_next(guild):
    guild_id = guild.id

    if guild.voice_client is None:
        return

    voice = guild.voice_client

    queue = get_queue(guild_id)

    # ถ้าเปิด loop เพลงปัจจุบัน
    if loop_mode.get(guild_id) and current_song.get(guild_id):
        song = current_song[guild_id]
    else:
        if not queue:
            current_song.pop(guild_id, None)

            try:
                await voice.disconnect()
            except Exception:
                pass

            return

        song = queue.pop(0)
        current_song[guild_id] = song

    try:
        source = discord.FFmpegPCMAudio(
            song["url"],
            executable=FFMPEG_PATH,
            **FFMPEG_OPTIONS
        )

    except Exception as e:
        print(
            f"[ERROR] FFmpeg source error: {e}"
        )

        await play_next(guild)
        return

    def after_playing(error):
        if error:
            print(
                f"[PLAYER ERROR] {error}"
            )

        asyncio.run_coroutine_threadsafe(
            play_next(guild),
            bot.loop
        )

    try:
        voice.play(
            source,
            after=after_playing
        )

    except Exception as e:
        print(
            f"[ERROR] Voice play error: {e}"
        )

        await play_next(guild)
        return

    channel = guild.system_channel

    if channel:
        embed = discord.Embed(
            title="🎵 กำลังเล่นเพลง",
            description=(
                f"**{song['title']}**\n\n"
                f"⏱️ {format_duration(song['duration'])}\n"
                f"👤 {song['uploader']}"
            )
        )

        if song.get("thumbnail"):
            embed.set_thumbnail(
                url=song["thumbnail"]
            )

        try:
            await channel.send(
                embed=embed
            )
        except Exception:
            pass


# ==================================================
# ENSURE VOICE
# ==================================================

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
            await voice.move_to(channel)

        return voice

    except Exception as e:
        print(
            f"[VOICE ERROR] {e}"
        )

        await ctx.send(
            "❌ ไม่สามารถเข้าห้องเสียงได้ครับ"
        )

        return None


# ==================================================
# BOT READY
# ==================================================

@bot.event
async def on_ready():
    print("=" * 50)
    print("🎵 DJ Pop Music Bot")
    print("=" * 50)
    print(f"Bot      : {bot.user}")
    print(f"Bot ID   : {bot.user.id}")
    print(f"Servers  : {len(bot.guilds)}")
    print(f"Python   : {os.sys.version}")
    print("=" * 50)
    print("✅ Bot is online!")
    print("=" * 50)


# ==================================================
# JOIN
# ==================================================

@bot.command()
async def join(ctx):
    voice = await ensure_voice(ctx)

    if voice:
        await ctx.send(
            f"🎧 เข้าห้อง **{voice.channel.name}** แล้วครับ"
        )


# ==================================================
# LEAVE
# ==================================================

@bot.command()
async def leave(ctx):
    voice = ctx.guild.voice_client

    if voice is None:
        await ctx.send(
            "❌ ตอนนี้บอทไม่ได้อยู่ในห้องเสียงครับ"
        )
        return

    queues[ctx.guild.id] = []
    current_song.pop(ctx.guild.id, None)
    loop_mode.pop(ctx.guild.id, None)

    await voice.disconnect()

    await ctx.send(
        "👋 ออกจากห้องเสียงแล้วครับ"
    )


# ==================================================
# PLAY
# ==================================================

@bot.command()
async def play(ctx, *, query=None):
    if not query:
        await ctx.send(
            "❌ ใช้แบบนี้ครับ\n"
            "`!play ชื่อเพลง`\n"
            "หรือ\n"
            "`!play https://youtube.com/...`"
        )
        return

    voice = await ensure_voice(ctx)

    if voice is None:
        return

    async with get_lock(ctx.guild.id):
        loading = await ctx.send(
            "🔎 กำลังค้นหาเพลง..."
        )

        try:
            song = await extract_song(query)

        except Exception as e:
            print(
                f"[YT-DLP ERROR] {e}"
            )

            await loading.edit(
                content=(
                    "❌ ค้นหาเพลงไม่สำเร็จครับ\n"
                    "ลองใช้ YouTube URL โดยตรงดูครับ"
                )
            )

            return

        if song is None or not song.get("url"):
            await loading.edit(
                content="❌ ไม่พบเพลงครับ"
            )
            return

        queue = get_queue(ctx.guild.id)

        # ถ้าบอทกำลังเล่นอยู่ ให้เพิ่มเข้าคิว
        if voice.is_playing() or voice.is_paused():
            queue.append(song)

            await loading.edit(
                content=(
                    f"📋 เพิ่มเข้าคิวแล้วครับ\n"
                    f"**{song['title']}**\n"
                    f"ลำดับที่ `{len(queue)}`"
                )
            )

            return

        # ยังไม่มีเพลงเล่น
        current_song[ctx.guild.id] = song

        await loading.delete()

        try:
            source = discord.FFmpegPCMAudio(
                song["url"],
                executable=FFMPEG_PATH,
                **FFMPEG_OPTIONS
            )

        except Exception as e:
            print(
                f"[FFMPEG ERROR] {e}"
            )

            await ctx.send(
                "❌ ไม่สามารถเปิดเสียงเพลงได้ครับ"
            )

            return

        def after_playing(error):
            if error:
                print(
                    f"[PLAYER ERROR] {error}"
                )

            asyncio.run_coroutine_threadsafe(
                play_next(ctx.guild),
                bot.loop
            )

        try:
            voice.play(
                source,
                after=after_playing
            )

        except Exception as e:
            print(
                f"[PLAY ERROR] {e}"
            )

            await ctx.send(
                "❌ ไม่สามารถเล่นเพลงได้ครับ"
            )

            return

        embed = discord.Embed(
            title="🎵 กำลังเล่นเพลง",
            description=(
                f"**{song['title']}**\n\n"
                f"⏱️ {format_duration(song['duration'])}\n"
                f"👤 {song['uploader']}"
            )
        )

        if song.get("thumbnail"):
            embed.set_thumbnail(
                url=song["thumbnail"]
            )

        await ctx.send(
            embed=embed
        )


# ==================================================
# SKIP
# ==================================================

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


# ==================================================
# PAUSE
# ==================================================

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
            "❌ ไม่มีเพลงที่กำลังเล่นครับ"
        )
        return

    voice.pause()

    await ctx.send(
        "⏸️ หยุดเพลงชั่วคราวแล้วครับ"
    )


# ==================================================
# RESUME
# ==================================================

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


# ==================================================
# STOP
# ==================================================

@bot.command()
async def stop(ctx):
    voice = ctx.guild.voice_client

    if voice is None:
        await ctx.send(
            "❌ บอทยังไม่ได้อยู่ในห้องเสียงครับ"
        )
        return

    queues[ctx.guild.id] = []

    if voice.is_playing() or voice.is_paused():
        voice.stop()

    current_song.pop(
        ctx.guild.id,
        None
    )

    await ctx.send(
        "⏹️ หยุดเพลงและล้างคิวแล้วครับ"
    )


# ==================================================
# QUEUE
# ==================================================

@bot.command(name="queue")
async def show_queue(ctx):
    queue = get_queue(ctx.guild.id)

    current = current_song.get(
        ctx.guild.id
    )

    if current is None and not queue:
        await ctx.send(
            "📭 ตอนนี้คิวว่างครับ"
        )
        return

    embed = discord.Embed(
        title="🎵 Music Queue"
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
            name="📋 คิว",
            value=text,
            inline=False
        )

    await ctx.send(
        embed=embed
    )


# ==================================================
# LOOP
# ==================================================

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


# ==================================================
# NOW PLAYING
# ==================================================

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

    embed = discord.Embed(
        title="🎵 Now Playing",
        description=(
            f"**{song['title']}**\n\n"
            f"⏱️ {format_duration(song['duration'])}\n"
            f"👤 {song['uploader']}"
        )
    )

    if song.get("thumbnail"):
        embed.set_thumbnail(
            url=song["thumbnail"]
        )

    await ctx.send(
        embed=embed
    )


# ==================================================
# HELP
# ==================================================

@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="🎵 DJ Pop Music Bot",
        description="คำสั่งทั้งหมดของบอท"
    )

    embed.add_field(
        name="🎧 เพลง",
        value=(
            "`!play <เพลง>` - เล่นเพลง\n"
            "`!skip` - ข้ามเพลง\n"
            "`!pause` - พักเพลง\n"
            "`!resume` - เล่นต่อ\n"
            "`!stop` - หยุดและล้างคิว\n"
            "`!queue` - ดูคิว\n"
            "`!nowplaying` - ดูเพลงปัจจุบัน\n"
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


# ==================================================
# COMMAND ERROR
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
            "❌ ข้อมูลไม่ครบครับ\n"
            "ใช้ `!help` เพื่อดูวิธีใช้"
        )
        return

    if isinstance(
        error,
        commands.CommandInvokeError
    ):
        print(
            f"[COMMAND ERROR] "
            f"{error.original}"
        )

        await ctx.send(
            "❌ เกิดข้อผิดพลาดระหว่างทำงานครับ"
        )

        return

    print(
        f"[ERROR] {error}"
    )


# ==================================================
# START BOT
# ==================================================

if __name__ == "__main__":
    print("🚀 Starting DJ Pop Bot...")

    bot.run(TOKEN)
