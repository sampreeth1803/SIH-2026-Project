from __future__ import annotations

import os
import subprocess
from pathlib import Path


def ffmpeg_executable() -> str:
    configured_path = os.environ.get("FFMPEG_PATH")
    if configured_path:
        executable = Path(configured_path)
        if executable.is_file():
            return str(executable)
        raise RuntimeError(f"FFMPEG_PATH does not point to a file: {executable}")

    try:
        import imageio_ffmpeg
    except ImportError as error:
        raise RuntimeError(
            "FFmpeg is required. Install dependencies with "
            "'python -m pip install -r requirements.txt', or set FFMPEG_PATH."
        ) from error

    return imageio_ffmpeg.get_ffmpeg_exe()


def find_tracking_video(directory: Path) -> Path | None:
    candidates = [*directory.glob("*.mp4"), *directory.glob("*.avi")]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def convert_to_mp4(source: Path, target: Path) -> Path:
    if source.suffix.lower() == ".mp4":
        return source

    target.parent.mkdir(parents=True, exist_ok=True)
    conversion = subprocess.run(
        [
            ffmpeg_executable(),
            "-y",
            "-i",
            str(source),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if conversion.returncode != 0 or not target.is_file():
        details = conversion.stderr.strip()[-1000:]
        raise RuntimeError(f"FFmpeg conversion failed: {details}")
    return target
