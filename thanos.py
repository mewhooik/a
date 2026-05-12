import os
import re
import time
import mmap
import shutil
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import tgcrypto
import subprocess
import concurrent.futures
from math import ceil
from pyrogram.errors import FloodWait
from utils import progress_bar
from pyrogram import Client, filters
from pyrogram.types import Message
from io import BytesIO
from pathlib import Path  
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
import math
import m3u8
from urllib.parse import urljoin
from vars import *
from db import Database
from compat import (
    IS_WINDOWS, CREATE_NO_WINDOW, find_binary, get_ffmpeg, get_ffprobe,
    get_mp4decrypt, get_aria2c, get_ytdlp,
    get_duration_ffprobe, run_shell_cmd,
)



def get_free_disk_mb():
    """Return free disk space in MB for the current working directory."""
    import shutil
    return shutil.disk_usage(".").free / (1024 * 1024)


def check_disk_space(required_mb=512):
    """Raise if free disk space is below required_mb. Prevents storage-related crashes."""
    free = get_free_disk_mb()
    if free < required_mb:
        raise Exception(
            f"⚠️ Not enough disk space: {free:.0f} MB free, need at least {required_mb} MB. "
            f"Use /clean to free up space."
        )


def get_duration(filename):
    return get_duration_ffprobe(filename)

def split_large_video(file_path, max_size_mb=1900):
    size_bytes = os.path.getsize(file_path)
    max_bytes = max_size_mb * 1024 * 1024

    if size_bytes <= max_bytes:
        return [file_path]  # No splitting needed

    duration = get_duration(file_path)
    parts = ceil(size_bytes / max_bytes)
    part_duration = duration / parts
    base_name = file_path.rsplit(".", 1)[0]
    output_files = []

    for i in range(parts):
        output_file = f"{base_name}_part{i+1}.mp4"
        cmd = [
            get_ffmpeg(), "-y",
            "-i", file_path,
            "-ss", str(int(part_duration * i)),
            "-t", str(int(part_duration)),
            "-c", "copy",
            output_file
        ]
        kwargs = {}
        if IS_WINDOWS:
            kwargs["creationflags"] = CREATE_NO_WINDOW
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
        if os.path.exists(output_file):
            output_files.append(output_file)

    # Delete original immediately after splitting to free disk space.
    # The caller must NOT delete it again after this point.
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass

    return output_files


def duration(filename):
    return get_duration_ffprobe(filename)


def get_mps_and_keys(api_url):
    response = requests.get(api_url)
    response_json = response.json()
    mpd = response_json.get('mpd_url')
    keys = response_json.get('keys')
    return mpd, keys


   
def exec(cmd):
        process = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output = process.stdout.decode()
        print(output)
        return output
        #err = process.stdout.decode()
def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        print("Waiting for tasks to complete")
        fut = executor.map(exec,cmds)
async def aio(url,name):
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url,name):
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka

async def pdf_download(url, file_name, chunk_size=1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name   
   

def parse_vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = []
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",2)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    new_info.append((i[0], i[2]))
            except:
                pass
    return new_info


def vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = dict()
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",3)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    
                    # temp.update(f'{i[2]}')
                    # new_info.append((i[2], i[0]))
                    #  mp4,mkv etc ==== f"({i[1]})" 
                    
                    new_info.update({f'{i[2]}':f'{i[0]}'})

            except:
                pass
    return new_info


async def download_and_decrypt_video(url, cmd, name, appxkey=None):
    """
    Download an AppX encrypted video and optionally decrypt with mp4decrypt.

    Args:
        url:     Direct CDN URL (.mkv / .m3u8)
        cmd:     yt-dlp fallback command string
        name:    Output base name (no extension)
        appxkey: "KID:KEY" hex string, or plain key, or None to skip decryption

    Returns: path to the final video file
    """
    output_mkv = f"{name}.mkv"
    output_mp4 = f"{name}.mp4"

    _curl_headers = (
        '-H "User-Agent: Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36" '
        '-H "Accept: */*" '
        '-H "Accept-Language: en-US,en;q=0.9" '
        '-H "Origin: https://app.classx.co.in" '
        '-H "Referer: https://app.classx.co.in/" '
    )
    dl_cmd = f'curl -L --fail --retry 3 --retry-delay 2 {_curl_headers} -o "{output_mkv}" "{url}"'
    ret = subprocess.run(dl_cmd, shell=True)

    _file_ok = ret.returncode == 0 and os.path.exists(output_mkv) and os.path.getsize(output_mkv) > 10_000
    if not _file_ok:
        if os.path.exists(output_mkv):
            _sz = os.path.getsize(output_mkv)
            logging.warning(f"curl produced suspicious file ({_sz} bytes), falling back")
            os.remove(output_mkv)
        else:
            logging.warning("curl failed for AppX — falling back to yt-dlp / ffmpeg")
        if '.m3u8' in url:
            _fb_cmd = f'ffmpeg -y -hide_banner -loglevel error -headers "Referer: https://app.classx.co.in/\r\nOrigin: https://app.classx.co.in\r\n" -i "{url}" -c copy "{output_mkv}"'
        else:
            _fb_cmd = f'{cmd} -R 5 --fragment-retries 5 --add-header "Referer:https://app.classx.co.in/" --add-header "Origin:https://app.classx.co.in"'
        subprocess.run(_fb_cmd, shell=True)
        for ext in [".mkv", ".mp4", ".webm"]:
            if os.path.exists(f"{name}{ext}") and os.path.getsize(f"{name}{ext}") > 10_000:
                output_mkv = f"{name}{ext}"
                break

    if not os.path.exists(output_mkv) or os.path.getsize(output_mkv) < 10_000:
        raise FileNotFoundError(f"AppX download produced no valid file for: {name}")

    if not appxkey or str(appxkey).strip() in ('', '/d', 'None'):
        ffmpeg_cmd = f'ffmpeg -y -hide_banner -loglevel error -i "{output_mkv}" -c copy "{output_mp4}"'
        ret2 = subprocess.run(ffmpeg_cmd, shell=True)
        if ret2.returncode == 0 and os.path.exists(output_mp4):
            if output_mkv != output_mp4 and os.path.exists(output_mkv):
                os.remove(output_mkv)
            return output_mp4
        return output_mkv

    mp4decrypt_bin = get_mp4decrypt()
    decrypted = f"{name}_dec.mp4"
    if ":" in str(appxkey):
        kid, key = appxkey.split(":", 1)
        decrypt_cmd = f'"{mp4decrypt_bin}" --key {kid}:{key} --show-progress "{output_mkv}" "{decrypted}"'
    else:
        decrypt_cmd = f'"{mp4decrypt_bin}" --key {appxkey} --show-progress "{output_mkv}" "{decrypted}"'

    subprocess.run(decrypt_cmd, shell=True)

    if os.path.exists(decrypted):
        if os.path.exists(output_mkv):
            os.remove(output_mkv)
        ffmpeg_cmd = f'ffmpeg -y -hide_banner -loglevel error -i "{decrypted}" -c copy "{output_mp4}"'
        subprocess.run(ffmpeg_cmd, shell=True)
        if os.path.exists(output_mp4):
            os.remove(decrypted)
            return output_mp4
        return decrypted

    raise FileNotFoundError(f"Decryption failed for: {name}")


async def decrypt_and_merge_video(mpd_url, keys_string, output_path, output_name, quality="720"):
    try:
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        _ytdlp = get_ytdlp()
        _aria2c = get_aria2c()
        cmd1 = f'"{_ytdlp}" -f "bv[height<={quality}]+ba/b" -o "{output_path}/file.%(ext)s" --allow-unplayable-format --no-check-certificate --external-downloader "{_aria2c}" "{mpd_url}"'
        print(f"Running command: {cmd1}")
        run_shell_cmd(cmd1)
        
        avDir = list(output_path.iterdir())
        print(f"Downloaded files: {avDir}")
        print("Decrypting")

        video_decrypted = False
        audio_decrypted = False

        _mp4decrypt = get_mp4decrypt()
        _ffmpeg = get_ffmpeg()
        for data in avDir:
            if data.suffix == ".mp4" and not video_decrypted:
                cmd2 = f'"{_mp4decrypt}" {keys_string} --show-progress "{data}" "{output_path}/video.mp4"'
                print(f"Running command: {cmd2}")
                run_shell_cmd(cmd2)
                if (output_path / "video.mp4").exists():
                    video_decrypted = True
                data.unlink()
            elif data.suffix == ".m4a" and not audio_decrypted:
                cmd3 = f'"{_mp4decrypt}" {keys_string} --show-progress "{data}" "{output_path}/audio.m4a"'
                print(f"Running command: {cmd3}")
                run_shell_cmd(cmd3)
                if (output_path / "audio.m4a").exists():
                    audio_decrypted = True
                data.unlink()

        if not video_decrypted or not audio_decrypted:
            raise FileNotFoundError("Decryption failed: video or audio file not found.")

        cmd4 = f'"{_ffmpeg}" -i "{output_path}/video.mp4" -i "{output_path}/audio.m4a" -c copy "{output_path}/{output_name}.mp4"'
        print(f"Running command: {cmd4}")
        run_shell_cmd(cmd4)
        if (output_path / "video.mp4").exists():
            (output_path / "video.mp4").unlink()
        if (output_path / "audio.m4a").exists():
            (output_path / "audio.m4a").unlink()
        
        filename = output_path / f"{output_name}.mp4"

        if not filename.exists():
            raise FileNotFoundError("Merged video file not found.")

        dur_val = get_duration_ffprobe(str(filename))
        print(f"Duration info: {dur_val}s")

        return str(filename)

    except Exception as e:
        print(f"Error during decryption and merging: {str(e)}")
        raise

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if proc.returncode == 1:
        return False
    if stdout:
        return f'[stdout]\n{stdout.decode()}'
    if stderr:
        return f'[stderr]\n{stderr.decode()}'

    

def old_download(url, file_name, chunk_size = 1024 * 10 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name


def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"


async def fast_download(url, name):
    """Fast direct download implementation without yt-dlp"""
    max_retries = 5
    retry_count = 0
    success = False
    
    while not success and retry_count < max_retries:
        try:
            if "m3u8" in url:
                # Handle m3u8 files
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        m3u8_text = await response.text()
                        
                    playlist = m3u8.loads(m3u8_text)
                    if playlist.is_endlist:
                        # Direct download of segments
                        base_url = url.rsplit('/', 1)[0] + '/'
                        
                        # Download all segments concurrently
                        segments = []
                        async with aiohttp.ClientSession() as session:
                            tasks = []
                            for segment in playlist.segments:
                                segment_url = urljoin(base_url, segment.uri)
                                task = asyncio.create_task(session.get(segment_url))
                                tasks.append(task)
                            
                            responses = await asyncio.gather(*tasks)
                            for response in responses:
                                segment_data = await response.read()
                                segments.append(segment_data)
                        
                        # Merge segments and save
                        output_file = f"{name}.mp4"
                        with open(output_file, 'wb') as f:
                            for segment in segments:
                                f.write(segment)
                        
                        success = True
                        return [output_file]
                    else:
                        # For live streams, fall back to ffmpeg
                        _ffmpeg = get_ffmpeg()
                        cmd = f'"{_ffmpeg}" -hide_banner -loglevel error -stats -i "{url}" -c copy -bsf:a aac_adtstoasc -movflags +faststart "{name}.mp4"'
                        run_shell_cmd(cmd)
                        if os.path.exists(f"{name}.mp4"):
                            success = True
                            return [f"{name}.mp4"]
            else:
                # For direct video URLs
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            output_file = f"{name}.mp4"
                            with open(output_file, 'wb') as f:
                                while True:
                                    chunk = await response.content.read(1024*1024)  # 1MB chunks
                                    if not chunk:
                                        break
                                    f.write(chunk)
                            success = True
                            return [output_file]
            
            if not success:
                print(f"\nAttempt {retry_count + 1} failed, retrying in 3 seconds...")
                retry_count += 1
                await asyncio.sleep(3)
                
        except Exception as e:
            print(f"\nError during attempt {retry_count + 1}: {str(e)}")
            retry_count += 1
            await asyncio.sleep(3)
    
    return None

def _is_yt_cookies_cmd(cmd: str) -> bool:
    return "player_client=web" in cmd and ("youtu.be" in cmd or "youtube.com" in cmd)


def _build_yt_fallback_cmd(cmd: str) -> str:
    """Build a fallback yt-dlp command using android_vr client without cookies.
    Used when web client fails due to cookie expiry or challenge errors."""
    import re as _re
    fallback = cmd
    # Remove --cookies <file> flag
    fallback = _re.sub(r'--cookies\s+\S+\s*', '', fallback)
    # Remove --username and --password flags
    fallback = _re.sub(r'--username\s+\S+\s*', '', fallback)
    fallback = _re.sub(r'--password\s+\S+\s*', '', fallback)
    # Replace player_client=web with android_vr
    fallback = fallback.replace('player_client=web', 'player_client=android_vr')
    # Remove --js-runtimes node (android_vr doesn't need JS)
    fallback = _re.sub(r'--js-runtimes\s+\S+\s*', '', fallback)
    return fallback.strip()


_COOKIE_CHALLENGE_KEYWORDS = [
    "Requested format is not available",
    "Only images are available",
    "n challenge solving failed",
    "No video formats found",
    "PO Token",
    "formats require a GVS PO Token",
]

_BOT_DETECTION_KEYWORDS = [
    "Sign in to confirm you're not a bot",
    "Sign in to confirm your age",
    "Use cookies-from-browser or cookies",
    "This helps protect our community",
]


async def download_video(url, cmd, name):
    check_disk_space(required_mb=512)
    retry_count = 0
    max_retries = 2
    last_stderr = ""
    _aria2c = get_aria2c()

    # HLS/m3u8 streams need --concurrent-fragments, not aria2c
    # aria2c cannot parallelize HLS segment downloads effectively
    is_hls = "m3u8" in url.lower() or ".m3u8" in cmd.lower()

    def _build_dl_cmd(base_cmd):
        if is_hls:
            # Use 4 concurrent fragments to keep memory low on constrained servers
            return f'{base_cmd} -R 25 --fragment-retries 25 --concurrent-fragments 4'
        else:
            return f'{base_cmd} -R 25 --fragment-retries 25 --external-downloader "{_aria2c}" --downloader-args "aria2c: -x 8 -j 8"'

    while retry_count < max_retries:
        download_cmd = _build_dl_cmd(cmd)
        print(download_cmd)
        logging.info(download_cmd)

        k = run_shell_cmd(download_cmd, capture=True)
        last_stderr = (k.stderr or "") + (k.stdout or "")

        if k.returncode == 0:
            break  # success

        # Detect hard bot detection → caller must provide credentials
        if any(kw.lower() in last_stderr.lower() for kw in _BOT_DETECTION_KEYWORDS):
            raise Exception(f"YouTube Bot Detection: {last_stderr.strip()[-300:]}")

        # Detect cookie/challenge failures on web client → try android_vr fallback
        is_challenge_fail = any(kw.lower() in last_stderr.lower() for kw in _COOKIE_CHALLENGE_KEYWORDS)
        if is_challenge_fail and _is_yt_cookies_cmd(cmd):
            fallback_cmd = _build_yt_fallback_cmd(cmd)
            fallback_dl_cmd = _build_dl_cmd(fallback_cmd)
            print(f"⚠️ Web client challenge failed, trying android_vr fallback...")
            logging.info(f"Fallback cmd: {fallback_dl_cmd}")
            k2 = run_shell_cmd(fallback_dl_cmd, capture=True)
            if k2.returncode == 0:
                break  # fallback succeeded
            last_stderr = (k2.stderr or "") + (k2.stdout or "")
            # If fallback also gets bot-detected, raise so caller can prompt for credentials
            if any(kw.lower() in last_stderr.lower() for kw in _BOT_DETECTION_KEYWORDS):
                raise Exception(f"YouTube Bot Detection: {last_stderr.strip()[-300:]}")

        retry_count += 1
        print(f"⚠️ Download failed (attempt {retry_count}/{max_retries}), retrying in 5s...\nReason: {last_stderr.strip()[-300:]}")
        await asyncio.sleep(5)

    # Locate the actual output file
    base = name.split(".")[0]
    for candidate in [name, f"{name}.webm", f"{base}.mkv", f"{base}.mp4", f"{base}.mp4.webm"]:
        if os.path.isfile(candidate):
            return candidate

    # No file found — download failed; raise so the caller can report the error
    short_err = last_stderr.strip()[-400:] if last_stderr.strip() else "unknown error (no stderr captured)"
    raise Exception(f"Download failed after {max_retries} attempts.\n{short_err}")





async def send_vid(bot: Client, m: Message, cc, filename, thumb, name, prog, channel_id, watermark="Thanos", topic_thread_id: int = None, display_name: str = None):
    try:
        temp_thumb = None  # ✅ Ensure this is always defined for later cleanup

        thumbnail = thumb
        if thumb in ["/d", "no"] or not os.path.exists(thumb):
            temp_thumb = os.path.join("downloads", f"thumb_{os.path.basename(filename)}.jpg")
            
            _ffmpeg = get_ffmpeg()
            _ffprobe = get_ffprobe()
            run_shell_cmd(
                f'"{_ffmpeg}" -i "{filename}" -ss 00:00:10 -vframes 1 -q:v 2 -y "{temp_thumb}"'
            )

            if os.path.exists(temp_thumb) and (watermark and watermark.strip() != "/d"):
                text_to_draw = watermark.strip()
                try:
                    kwargs = {}
                    if IS_WINDOWS:
                        kwargs["creationflags"] = CREATE_NO_WINDOW
                    probe_out = subprocess.check_output(
                        f'"{_ffprobe}" -v error -select_streams v:0 -show_entries stream=width -of csv=p=0:s=x "{temp_thumb}"',
                        shell=True,
                        stderr=subprocess.DEVNULL,
                        **kwargs,
                    ).decode().strip()
                    img_width = int(probe_out.split('x')[0]) if 'x' in probe_out else int(probe_out)
                except Exception:
                    img_width = 1280

                # Base size relative to width, then adjust by text length
                base_size = max(28, int(img_width * 0.075))
                text_len = len(text_to_draw)
                if text_len <= 3:
                    font_size = int(base_size * 1.25)
                elif text_len <= 8:
                    font_size = int(base_size * 1.0)
                elif text_len <= 15:
                    font_size = int(base_size * 0.85)
                else:
                    font_size = int(base_size * 0.7)
                font_size = max(32, min(font_size, 120))

                box_h = max(60, int(font_size * 1.6))

                # Simple escaping for single quotes in text
                safe_text = text_to_draw.replace("'", "\\'")

                text_cmd = (
                    f'"{_ffmpeg}" -i "{temp_thumb}" -vf '
                    f'"drawbox=y=0:color=black@0.35:width=iw:height={box_h}:t=fill,'
                    f'drawtext=fontfile=font.ttf:text=\'{safe_text}\':fontcolor=white:'
                    f'fontsize={font_size}:x=(w-text_w)/2:y=(({box_h})-text_h)/2" '
                    f'-c:v mjpeg -q:v 2 -y "{temp_thumb}"'
                )
                run_shell_cmd(text_cmd)
            
            thumbnail = temp_thumb if os.path.exists(temp_thumb) else None

        await prog.delete(True)  # ⏳ Remove previous progress message

        _label = display_name if display_name else name
        try:
            reply1 = await bot.send_message(channel_id, f" **Uploading Video:**\n<blockquote>{_label}</blockquote>", message_thread_id=topic_thread_id)
        except FloodWait as e:
            await m.reply_text(f"⏳ FloodWait: waiting {e.value} seconds...")
            await asyncio.sleep(e.value)
            reply1 = await bot.send_message(channel_id, f" **Uploading Video:**\n<blockquote>{_label}</blockquote>", message_thread_id=topic_thread_id)
        reply = await m.reply_text(f"🖼 **Generating Thumbnail:**\n<blockquote>{_label}</blockquote>")

        file_size_mb = os.path.getsize(filename) / (1024 * 1024)
        notify_split = None
        sent_message = None

        if file_size_mb < 2000:
            # 📹 Upload as single video
            dur = int(duration(filename))
            start_time = time.time()
            _ext = os.path.splitext(filename)[1] or ".mp4"
            _file_name = f"{_label}{_ext}"

            try:
                sent_message = await bot.send_video(
                    chat_id=channel_id,
                    video=filename,
                    caption=cc,
                    file_name=_file_name,
                    supports_streaming=True,
                    height=720,
                    width=1280,
                    thumb=thumbnail,
                    duration=dur,
                    progress=progress_bar,
                    progress_args=(reply, start_time),
                    message_thread_id=topic_thread_id
                )
            except FloodWait as e:
                await m.reply_text(f"⏳ FloodWait: waiting {e.value} seconds...")
                await asyncio.sleep(e.value)
                sent_message = await bot.send_video(
                    chat_id=channel_id,
                    video=filename,
                    caption=cc,
                    file_name=_file_name,
                    supports_streaming=True,
                    height=720,
                    width=1280,
                    thumb=thumbnail,
                    duration=dur,
                    progress=progress_bar,
                    progress_args=(reply, time.time()),
                    message_thread_id=topic_thread_id
                )
            except Exception:
                try:
                    sent_message = await bot.send_document(
                        chat_id=channel_id,
                        document=filename,
                        caption=cc,
                        file_name=_file_name,
                        progress=progress_bar,
                        progress_args=(reply, start_time),
                        message_thread_id=topic_thread_id
                    )
                except FloodWait as e:
                    await m.reply_text(f"⏳ FloodWait: waiting {e.value} seconds...")
                    await asyncio.sleep(e.value)
                    sent_message = await bot.send_document(
                        chat_id=channel_id,
                        document=filename,
                        caption=cc,
                        file_name=_file_name,
                        progress=progress_bar,
                        progress_args=(reply, time.time()),
                        message_thread_id=topic_thread_id
                    )

            # ✅ Cleanup
            if os.path.exists(filename):
                os.remove(filename)
            await reply.delete(True)
            await reply1.delete(True)

        else:
            # ⚠️ Notify about splitting
            notify_split = await m.reply_text(
                f"⚠️ The video is larger than 2GB ({human_readable_size(os.path.getsize(filename))})\n"
                f"⏳ Splitting into parts before upload..."
            )

            parts = split_large_video(filename)

            try:
                first_part_message = None
                for idx, part in enumerate(parts):
                    part_dur = int(duration(part))
                    part_num = idx + 1
                    total_parts = len(parts)
                    part_caption = f"{cc}\n\n📦 Part {part_num} of {total_parts}"
                    part_filename = f"{name}_Part{part_num}.mp4"

                    upload_msg = await m.reply_text(f"📤 Uploading Part {part_num}/{total_parts}...")

                    try:
                        msg_obj = await bot.send_video(
                            chat_id=channel_id,
                            video=part,
                            caption=part_caption,
                            file_name=part_filename,
                            supports_streaming=True,
                            height=720,
                            width=1280,
                            thumb=thumbnail,
                            duration=part_dur,
                            progress=progress_bar,
                            progress_args=(upload_msg, time.time()),
                            message_thread_id=topic_thread_id
                        )
                        if first_part_message is None:
                            first_part_message = msg_obj
                    except FloodWait as e:
                        await m.reply_text(f"⏳ FloodWait: waiting {e.value} seconds...")
                        await asyncio.sleep(e.value)
                        msg_obj = await bot.send_video(
                            chat_id=channel_id,
                            video=part,
                            caption=part_caption,
                            file_name=part_filename,
                            supports_streaming=True,
                            height=720,
                            width=1280,
                            thumb=thumbnail,
                            duration=part_dur,
                            progress=progress_bar,
                            progress_args=(upload_msg, time.time()),
                            message_thread_id=topic_thread_id
                        )
                        if first_part_message is None:
                            first_part_message = msg_obj
                    except Exception:
                        try:
                            msg_obj = await bot.send_document(
                                chat_id=channel_id,
                                document=part,
                                caption=part_caption,
                                file_name=part_filename,
                                progress=progress_bar,
                                progress_args=(upload_msg, time.time()),
                                message_thread_id=topic_thread_id
                            )
                            if first_part_message is None:
                                first_part_message = msg_obj
                        except FloodWait as e:
                            await m.reply_text(f"⏳ FloodWait: waiting {e.value} seconds...")
                            await asyncio.sleep(e.value)
                            msg_obj = await bot.send_document(
                                chat_id=channel_id,
                                document=part,
                                caption=part_caption,
                                file_name=part_filename,
                                progress=progress_bar,
                                progress_args=(upload_msg, time.time()),
                                message_thread_id=topic_thread_id
                            )
                            if first_part_message is None:
                                first_part_message = msg_obj

                    await upload_msg.delete(True)
                    if os.path.exists(part):
                        os.remove(part)

            except Exception as e:
                raise Exception(f"Upload failed at part {idx + 1}: {str(e)}")

            # ✅ Final messages
            if len(parts) > 1:
                await m.reply_text("✅ Large video successfully uploaded in multiple parts!")

            # Cleanup after split
            await reply.delete(True)
            await reply1.delete(True)
            if notify_split:
                await notify_split.delete(True)
            # Note: split_large_video already deleted the original file to free disk space early

            # Return first sent part message
            sent_message = first_part_message

        # 🧹 Cleanup generated thumbnail if applicable
        if thumb in ["/d", "no"] and temp_thumb and os.path.exists(temp_thumb):
            os.remove(temp_thumb)

        return sent_message

    except Exception as err:
        import traceback
        logging.error(f"send_vid failed: {err}\n{traceback.format_exc()}")
        # Guaranteed cleanup so disk space is never leaked on failure
        try:
            if filename and os.path.exists(filename):
                os.remove(filename)
        except Exception:
            pass
        try:
            if temp_thumb and os.path.exists(temp_thumb):
                os.remove(temp_thumb)
        except Exception:
            pass
        raise Exception(f"send_vid failed: {err}")



async def resolve_appx_url(url, quality="720"):
    """
    Resolve AppX signed URL to a direct CDN video URL.
    URL formats:
      Video: https://appxsignurl-omega.vercel.app/appx/<domain>/<path>.m3u8?usertoken=TOKEN&appxv=2
      PDF:   https://appxsignurl-omega.vercel.app/appx/<domain>/<path>.pdf?pdf=1&usertoken=TOKEN&appxv=2
    Returns: (resolved_url, title, encryption_key, content_type)
             where content_type is "pdf" or "video"
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                raise Exception(f"AppX API returned HTTP {resp.status}")
            data = await resp.json(content_type=None)

    if not data.get("success"):
        raise Exception(f"AppX API error: {data}")

    title = data.get("title", "file")
    content_type = "pdf" if data.get("type") == "pdf" or not data.get("is_video", True) else "video"

    if content_type == "pdf":
        pdf_url = data.get("pdf_url", "")
        if not pdf_url:
            raise Exception("No pdf_url in AppX PDF response")
        logging.info(f"AppX PDF resolved: title={title!r} url={pdf_url[:80]}...")
        return pdf_url, title, "", "pdf"

    encryption_key = data.get("encryption_key", "")
    all_qualities = data.get("all_qualities", [])
    video_url = data.get("video_url", "")

    quality_str = f"{quality}p"
    matched_url = None
    for q in all_qualities:
        if q.get("quality") == quality_str:
            matched_url = q.get("url")
            break

    if not matched_url:
        matched_url = all_qualities[0].get("url", video_url) if all_qualities else video_url

    if not matched_url:
        raise Exception("No video URL found in AppX API response")

    logging.info(f"AppX video resolved: title={title!r} quality={quality_str} url={matched_url[:80]}...")
    return matched_url, title, encryption_key, "video"

async def download_drm_mpd(input_string, quality="720", name=None):
    save_name = None
    output_path = None
    try:
        # Plain MPD URL — no DRM keys, download directly with yt-dlp
        if "*" not in input_string:
            url = input_string.strip()
            if not url:
                logging.error("download_drm_mpd: empty URL")
                return None

            safe_ts = re.sub(r'[^A-Za-z0-9_-]', '', str(int(time.time())))
            safe_name = re.sub(r'[\\/:*?"<>|]', '_', name.strip()) if name else f"Output_Video_{safe_ts}"
            save_name = safe_name
            output_path = Path(f"downloads/mpd_{safe_ts}")
            output_path.mkdir(parents=True, exist_ok=True)

            _ytdlp = get_ytdlp()
            _ffmpeg = get_ffmpeg()
            final_file = f"{save_name}.mkv"

            dl_cmd = (
                f'"{_ytdlp}" -f "bv[height<={quality}]+ba/b[ext=m4a]/bv+ba/b" '
                f'-o "{output_path}/file.%(ext)s" '
                f'--no-check-certificate '
                f'--no-part --concurrent-fragments 16 '
                f'"{url}"'
            )
            logging.info(f"Plain MPD download cmd: {dl_cmd}")
            dl_process = await asyncio.create_subprocess_shell(
                dl_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await dl_process.communicate()
            if stdout:
                logging.info(f"[yt-dlp stdout]\n{stdout.decode(errors='replace')}")
            if stderr:
                logging.info(f"[yt-dlp stderr]\n{stderr.decode(errors='replace')}")

            av_files = list(output_path.iterdir())
            logging.info(f"Plain MPD downloaded files: {av_files}")

            if not av_files:
                logging.error("Plain MPD: no files downloaded")
                _cleanup_temp_dir(output_path)
                return None

            video_file = None
            audio_file = None
            for f in av_files:
                if f.suffix in ('.mp4', '.mkv', '.webm') and video_file is None:
                    video_file = f
                elif f.suffix in ('.m4a', '.aac', '.opus', '.ogg') and audio_file is None:
                    audio_file = f

            if video_file and audio_file:
                merge_cmd = (
                    f'"{_ffmpeg}" -y -i "{video_file}" -i "{audio_file}" '
                    f'-c copy "{final_file}"'
                )
                logging.info(f"Plain MPD merge cmd: {merge_cmd}")
                merge_proc = await asyncio.create_subprocess_shell(
                    merge_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await merge_proc.communicate()
                _cleanup_temp_dir(output_path)
                if os.path.isfile(final_file):
                    logging.info(f"Plain MPD success: {final_file}")
                    return final_file
            elif video_file:
                dest = f"{save_name}{video_file.suffix}"
                shutil.move(str(video_file), dest)
                _cleanup_temp_dir(output_path)
                if os.path.isfile(dest):
                    logging.info(f"Plain MPD success (video only): {dest}")
                    return dest

            logging.error("Plain MPD: merge/move failed")
            _cleanup_temp_dir(output_path)
            return None

        # DRM MPD — format: url*startNumber:kid:key
        if ":" not in input_string:
            logging.error(f"Invalid DRM input format: {input_string}")
            return None

        url, remainder = input_string.split("*", 1)
        start_number, kid, key = remainder.split(":", 2)

        if not all([url, start_number, kid, key]):
            logging.error(f"One or more parsed fields are empty: url={url}, startNumber={start_number}")
            return None

        safe_start = re.sub(r'[^A-Za-z0-9_-]', '', start_number)
        if not safe_start:
            safe_start = "0"

        safe_given = re.sub(r'[\\/:*?"<>|]', '_', name.strip()) if name else None
        save_name = safe_given if safe_given else f"Output_Video_{safe_start}"
        output_path = Path(f"downloads/drm_{safe_start}")
        output_path.mkdir(parents=True, exist_ok=True)

        keys_string = f"--key {kid}:{key}"
        mp4decrypt_path = get_mp4decrypt()

        logging.info(f"Starting DRM MPD download: url={url}, startNumber={start_number}")

        _ytdlp = get_ytdlp()
        dl_cmd = (
            f'"{_ytdlp}" -f "bv[height<={quality}]+ba/b[ext=m4a]/bv+ba/b" '
            f'-o "{output_path}/file.%(ext)s" '
            f'--allow-unplayable-format --no-check-certificate '
            f'--no-part --concurrent-fragments 16 '
            f'"{url}"'
        )
        logging.info(f"Download cmd: {dl_cmd}")
        dl_process = await asyncio.create_subprocess_shell(
            dl_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await dl_process.communicate()
        if stdout:
            logging.info(f"[yt-dlp stdout]\n{stdout.decode(errors='replace')}")
        if stderr:
            logging.info(f"[yt-dlp stderr]\n{stderr.decode(errors='replace')}")

        av_files = list(output_path.iterdir())
        logging.info(f"Downloaded files: {av_files}")

        video_decrypted = False
        audio_decrypted = False

        for data in av_files:
            if data.suffix == ".mp4" and not video_decrypted:
                dec_cmd = f'"{mp4decrypt_path}" {keys_string} --show-progress "{data}" "{output_path}/video.mp4"'
                logging.info(f"Decrypt video: {dec_cmd}")
                run_shell_cmd(dec_cmd)
                if (output_path / "video.mp4").exists():
                    video_decrypted = True
                data.unlink()
            elif data.suffix == ".m4a" and not audio_decrypted:
                dec_cmd = f'"{mp4decrypt_path}" {keys_string} --show-progress "{data}" "{output_path}/audio.m4a"'
                logging.info(f"Decrypt audio: {dec_cmd}")
                run_shell_cmd(dec_cmd)
                if (output_path / "audio.m4a").exists():
                    audio_decrypted = True
                data.unlink()

        if not video_decrypted or not audio_decrypted:
            logging.error("Decryption failed: video or audio file not found.")
            _cleanup_temp_dir(output_path)
            return None

        final_file = f"{save_name}.mkv"
        _ffmpeg = get_ffmpeg()
        merge_cmd = f'"{_ffmpeg}" -y -i "{output_path}/video.mp4" -i "{output_path}/audio.m4a" -c copy "{final_file}"'
        logging.info(f"Merge cmd: {merge_cmd}")
        merge_process = await asyncio.create_subprocess_shell(
            merge_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await merge_process.communicate()

        _cleanup_temp_dir(output_path)

        if os.path.isfile(final_file):
            logging.info(f"Download successful: {final_file}")
            return final_file

        logging.error(f"Output file not found after merge.")
        return None

    except ValueError:
        logging.error(f"Failed to parse input string: {input_string}")
        _cleanup_temp_dir(output_path)
        return None
    except Exception as e:
        logging.error(f"download_drm_mpd error: {e}")
        _cleanup_temp_dir(output_path)
        return None


def _cleanup_temp_dir(dir_path):
    if dir_path and os.path.isdir(dir_path):
        shutil.rmtree(dir_path, ignore_errors=True)
        logging.info(f"Cleaned up temp directory: {dir_path}")
