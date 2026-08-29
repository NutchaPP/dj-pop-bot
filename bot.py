import os
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp


# ==================================================
# โหลด Token
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

    # ไม่บังคับ ext / format ที่อาจไม่มี
    "format": "bestaudio/best",

    "noplaylist": True,

    "quiet": True,

    "no_warnings": False,

    "default_search": "ytsearch1",

    "source_address": "0.0.0.0",

    "geo_bypass": True,

    "nocheckcertificate": True,

    # ใช้ cookies.txt
    "cookiefile": COOKIES_FILE,

    # Client ที่มีโอกาสใช้งานได้
    "extractor_args": {
        "youtube": {
            "player_client": [
                "web",
                "android",
                "ios"
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
# ตรวจ cookies.txt
# ==================================================

print("=" * 60)

if os.path.exists(COOKIES_FILE):

    print("✅ พบ cookies.txt")
    print(f"📁 ตำแหน่ง: {COOKIES_FILE}")

else:

    print("⚠️ ไม่พบ cookies.txt")
    print(f"📁 ตำแหน่งที่ต้องการ: {COOKIES_FILE}")

print("=" * 60)


# ==================================================
# ค้นหาเพลง
# ==================================================

async def search_song(search):

    loop = asyncio.get_running_loop()

    def extract():

        # --------------------------------------------------
        # วิธีที่ 1
        # --------------------------------------------------

        try:

            options = YTDL_OPTIONS.copy()

            with yt_dlp.YoutubeDL(options) as ydl:

                print("=" * 60)
                print(f"🔎 กำลังค้นหา: {search}")
                print("=" * 60)

                info = ydl.extract_info(
                    f"ytsearch1:{search}",
                    download=False
                )

                return info

        except Exception as first_error:

            print("=" * 60)
            print("⚠️ วิธีค้นหาหลักไม่สำเร็จ")
            print(
                f"{type(first_error).__name__}: "
                f"{first_error}"
            )
            print("🔄 กำลังลอง fallback...")
            print("=" * 60)

            # --------------------------------------------------
            # วิธีที่ 2 - ใช้ URL โดยตรงถ้าผู้ใช้ส่ง YouTube URL
            # --------------------------------------------------

            if search.startswith(
                (
                    "https://www.youtube.com/",
                    "https://youtu.be/",
                    "http://www.youtube.com/",
                    "http://youtu.be/"
                )
            ):

                fallback_options = {

                    "format": "bestaudio/best",

                    "noplaylist": True,

                    "quiet": True,

                    "no_warnings": False,

                    "cookiefile": COOKIES_FILE,

                    "source_address": "0.0.0.0",

                    "nocheckcertificate": True,
                }

                with yt_dlp.YoutubeDL(
                    fallback_options
                ) as ydl:

                    return ydl.extract_info(
                        search,
                        download=False
                    )

            raise first_error


    try:

        info = await loop.run_in_executor(
            None,
            extract
        )

        # --------------------------------------------------
        # Search Result
        # --------------------------------------------------

        entries = info.get("entries")

        if not entries:

            return None

        song = entries[0]

        # --------------------------------------------------
        # ตรวจ URL
        # --------------------------------------------------

        audio_url = song.get("url")

        if not audio_url:

            # บางกรณี search result ยังไม่มี direct URL
            webpage_url = song.get(
                "webpage_url"
            )

            if webpage_url:

                print(
                    "🔄 กำลังดึงข้อมูลเพลงจาก URL..."
                )

                direct_options = {

                    "format": "bestaudio/best",

                    "noplaylist": True,

                    "quiet": True,

                    "cookiefile": COOKIES_FILE,

                    "source_address": "0.0.0.0",

                    "nocheckcertificate": True,
                }

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

                    song = direct_info

        if not audio_url:

            raise RuntimeError(
                "ไม่พบ Audio URL จาก YouTube"
            )

        # --------------------------------------------------
        # คืนข้อมูลเพลง
        # --------------------------------------------------

        return {

            "title": song.get(
                "title",
                search
            ),

            "url": audio_url,

            "webpage_url": song.get(
                "webpage_url"
            ),
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
    # เพลงเล่นจบ
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

        # --------------------------------------------
        # ไม่พบเพลง
        # --------------------------------------------

        if song is None:

            await message.edit(
                content="❌ หาเพลงไม่เจอครับ"
            )

            return

        # --------------------------------------------
        # มีเพลงกำลังเล่น
        # --------------------------------------------

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

        # --------------------------------------------
        # ไม่มีเพลงเล่น
        # --------------------------------------------

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
