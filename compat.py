import os
import sys
import shutil
import subprocess

IS_WINDOWS = os.name == "nt"

CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def find_binary(name):
    if IS_WINDOWS:
        exe_name = name if name.endswith(".exe") else f"{name}.exe"
    else:
        exe_name = name

    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), exe_name)
    if os.path.isfile(local_path):
        return local_path

    found = shutil.which(exe_name)
    if found:
        return found

    if IS_WINDOWS:
        found_no_ext = shutil.which(name)
        if found_no_ext:
            return found_no_ext

    return name


def get_ffmpeg():
    return find_binary("ffmpeg")


def get_ffprobe():
    return find_binary("ffprobe")


def get_mp4decrypt():
    return find_binary("mp4decrypt")


def get_aria2c():
    return find_binary("aria2c")


def get_ytdlp():
    return find_binary("yt-dlp")


def get_duration_ffprobe(filename):
    ffprobe = get_ffprobe()
    kwargs = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = CREATE_NO_WINDOW
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **kwargs,
    )
    output = result.stdout.decode().strip()
    if not output:
        return 0.0
    try:
        return float(output)
    except ValueError:
        return 0.0


def safe_quote(s):
    if IS_WINDOWS:
        if not s or any(c in s for c in ' &|<>^"'):
            return '"' + s.replace('"', '\\"') + '"'
        return s
    else:
        import shlex
        return shlex.quote(s)


def run_shell_cmd(cmd, capture=False):
    kwargs = {}
    if IS_WINDOWS:
        kwargs["creationflags"] = CREATE_NO_WINDOW

    if capture:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, **kwargs
        )
        return result
    else:
        subprocess.run(cmd, shell=True, **kwargs)
        return None


def restart_process():
    os.execl(sys.executable, sys.executable, *sys.argv)
