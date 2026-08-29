import os
import asyncio

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
        "ไม่พบ DISCORD_TOKEN ใน Environment Variables"
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

BASE_DIR = "/home/container"

COOKIES_FILE = os.path.join(
    BASE_DIR,
    "cookies.txt"
)


# ==================================================
# yt-dlp OPTIONS
# ==================================================

YTDL_OPTIONS = {

    # เลือก audio ที่มีอยู่จริง
    "format": "bestaudio/best",

    "noplaylist": True,

    "quiet": True,

    "no_warnings": False,

    "default_search": "ytsearch1",

    "source_address": "0.0.0.0",

    "geo_bypass": True,

    "nocheckcertificate": True,

    # ------------------------------------------------
    # Cookies
    # ------------------------------------------------

    "cookiefile": COOKIES_FILE,

    # ------------------------------------------------
    # JavaScript Runtime
    # ใช้สำหรับ YouTube EJS challenge
    # ------------------------------------------------

    "js_runtimes": {
        "node": {}
    },

    # ------------------------------------------------
    # YouTube Client
    # ------------------------------------------------

    "extractor_args": {
        "youtube": {
            "player_client": [
                "web"
            ]
        }
    },
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

    "options": "-vn",
}


# ==================================================
# Queue
# ==================================================

music_queue = []

current_song = None


# ==================================================
# ตรวจสอบไฟล์ Cookies
# ==================================================

print("=" * 60)

if os.path.exists(COOKIES_FILE):

    print("✅ พบ cookies.txt")
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
# ตรวจสอบ Node.js
# ==================================================

async def check_node():

    loop = asyncio.get_running_loop()

    def run_check():

        return os.system(
            "node --version > /tmp/node_version.txt 2>&1"
        )

    try:

        result = await loop.run_in_executor(
            None,
            run_check
        )

        if result == 0:

            try:

                with open(
                    "/tmp/node_version.txt",
                    "r",
                    encoding="utf-8"
                ) as file:

                    version = file.read().strip()

                print("=" * 60)
                print("✅ พบ Node.js")
                print(f"📦 Version: {version}")
                print("=" * 60)

            except Exception:

                print("✅ พบ Node.js")

        else:

            print("=" * 60)
            print("⚠️ ไม่พบ Node.js")
            print(
                "yt-dlp อาจไม่สามารถแก้ YouTube EJS challenge ได้"
            )
            print("=" * 60)

    except Exception as e:

        print("=" * 60)
        print("⚠️ ตรวจสอบ Node.js ไม่สำเร็จ")
        print(
            f"{type(e).__name__}: {e}"
        )
        print("=" * 60)


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

        with yt_dlp.YoutubeDL(
            YTDL_OPTIONS
        ) as ydl:

            info = ydl.extract_info(
                f"ytsearch1:{search}",
                download=False
            )

            return info

    try:

        info = await loop.run_in_executor(
            None,
            extract
        )

        entries = info.get("entries")

        if not entries:

            return None

        song = entries[0]

        title = song.get(
            "title",
            search
        )

        webpage_url = song.get(
            "webpage_url"
        )

        audio_url = song.get(
            "url"
        )

        # ------------------------------------------------
        # ถ้ายังไม่มี Audio URL
        # ให้ดึงข้อมูลจากหน้า Video โดยตรง
        # ------------------------------------------------

        if not audio_url and webpage_url:

            print(
                "🔄 กำลังดึง Audio URL จาก Video..."
            )

            direct_options = YTDL_OPTIONS.copy()

            with yt_dlp.YoutubeDL(
                direct_options
            ) as ydl:

                direct_info = ydl.extract_info(
                    webpage_url,
                    download=False
                )

                audio_url = direct_info.get(
                    "url"
                )

                title = direct_info.get(
                    "title",
                    title
                )

        if not audio_url:

            raise RuntimeError(
                "ไม่พบ Audio URL จาก YouTube"
            )

        print("=" * 60)
        print("✅ พบเพลง")
        print(f"🎵 {title}")
        print("=" * 60)

        return {

            "title": title,

            "url": audio_url,

            "webpage_url": webpage_url,
        }

    except Exception as e:

        print("=" * 60)
        print("❌ YOUTUBE SEARCH ERROR")
        print(
            f"ประเภท: {type(e).__name__}"
        )
        print(
            f"รายละเอียด: {e}"
        )
        print("=" * 60)

        raise


# ==================================================
# เล่นเพลงถัดไป
# ==================================================

async def play_next(ctx):

    global current_song

    voice = ctx.voice_client

    if voice is None:

        return

    # ------------------------------------------------
    # Queue หมด
    # ------------------------------------------------

    if not music_queue:

        current_song = None

        await ctx.send(
            "📭 เพลงในคิวหมดแล้วครับ"
        )

        return

    # ------------------------------------------------
    # เอาเพลงออกจาก Queue
    # ------------------------------------------------

    current_song = music_queue.pop(0)

    title = current_song["title"]

    audio_url = current_song["url"]

    # ------------------------------------------------
    # FFmpeg
    # ------------------------------------------------

    try:

        source = discord.FFmpegPCMAudio(
            audio_url,
            executable="ffmpeg",
            **FFMPEG_OPTIONS
        )

    except Exception as e:

        print("=" * 60)
        print("❌ FFMPEG ERROR")
        print(
            f"ประเภท: {type(e).__name__}"
        )
        print(
            f"รายละเอียด: {e}"
        )
        print("=" * 60)

        await ctx.send(
            "❌ เปิดเสียงเพลงไม่ได้ครับ\n"
            f"`{type(e).__name__}: {e}`"
        )

        current_song = None

        return

    # ------------------------------------------------
    # Callback เมื่อเพลงจบ
    # ------------------------------------------------

    def after_playing(error):

        if error:

            print(
                f"❌ Audio Error: {error}"
            )

        asyncio.run_coroutine_threadsafe(
            play_next(ctx),
            bot.loop
        )

    # ------------------------------------------------
    # เริ่มเล่น
    # ------------------------------------------------

    try:

        voice.play(
            source,
            after=after_playing
        )

    except Exception as e:

        print("=" * 60)
        print("❌ VOICE PLAY ERROR")
        print(
            f"ประเภท: {type(e).__name__}"
        )
        print(
            f"รายละเอียด: {e}"
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
# Bot Online
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

    # ตรวจ Node.js
    await check_node()


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

    channel = ctx.author.voice.channel

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
            f"ประเภท: {type(e).__name__}"
        )
        print(
            f"รายละเอียด: {e}"
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

    # ------------------------------------------------
    # ตรวจ Voice
    # ------------------------------------------------

    if ctx.author.voice is None:

        await ctx.send(
            "❌ ป๊อปต้องเข้าห้องพูดก่อนครับ"
        )

        return

    # ------------------------------------------------
    # Connect Voice
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
    # กำลังค้นหา
    # ------------------------------------------------

    message = await ctx.send(
        f"🔎 กำลังค้นหา **{search}** ..."
    )

    try:

        song = await search_song(search)

        # ------------------------------------------------
        # ไม่พบ
        # ------------------------------------------------

        if song is None:

            await message.edit(
                content="❌ หาเพลงไม่เจอครับ"
            )

            return

        # ------------------------------------------------
        # มีเพลงกำลังเล่น
        # ------------------------------------------------

        if (
            voice.is_playing()
            or voice.is_paused()
        ):

            music_queue.append(song)

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
        # ไม่มีเพลงเล่น
        # ------------------------------------------------

        music_queue.append(song)

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

    await ctx.send(text)


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
async def on_command_error(ctx, error):

    if isinstance(
        error,
        commands.CommandNotFound
    ):

        return

    print("=" * 60)
    print("❌ COMMAND ERROR")
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

bot.run(TOKEN)
