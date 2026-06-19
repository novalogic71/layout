from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path


def wav_frame_count(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as handle:
            return int(handle.getnframes())
    except Exception:
        return 0


def wav_sample_rate(path: Path) -> int | None:
    try:
        with wave.open(str(path), "rb") as handle:
            return int(handle.getframerate())
    except Exception:
        return None


def copy_or_normalize_wav(
    source_path: Path,
    output_path: Path,
    normalize_audio: bool,
) -> tuple[bool, str | None]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not normalize_audio:
        shutil.copy2(source_path, output_path)
        return True, None

    sample_rate = wav_sample_rate(source_path)
    if sample_rate == 44100:
        shutil.copy2(source_path, output_path)
        return True, None

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        shutil.copy2(source_path, output_path)
        return False, f"ffmpeg not found; copied without resampling: {source_path.name}"

    cmd = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-ar",
        "44100",
        "-acodec",
        "pcm_s16le",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return True, None

    shutil.copy2(source_path, output_path)
    return (
        False,
        f"ffmpeg resample failed; copied original audio for {source_path.name}: {proc.stderr.strip()}",
    )

