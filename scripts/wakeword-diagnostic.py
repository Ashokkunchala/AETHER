"""Short local microphone probe; audio stays in memory and is not transmitted."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aether.config.settings import config  # noqa: E402
from aether.core.wakeword.wakeword_detector import WakeWordDetector  # noqa: E402

models_dir = Path(config.wakeword_models_dir)
if not models_dir.is_absolute():
    models_dir = ROOT / models_dir

phrase = config.wakeword_model.replace("_", " ").title()
detector = WakeWordDetector(
    model_name=config.wakeword_model,
    threshold=config.wakeword_threshold,
    models_dir=models_dir,
)
if not detector.available or detector.model is None:
    raise SystemExit(f"The configured {phrase} wake-word model is unavailable.")

stats = {"frames": 0, "sum_squares": 0.0, "max_level": 0.0, "max_score": 0.0}


def on_audio(indata, _frames, _time_info, status):
    if status:
        print(f"Audio input warning: {status}", flush=True)
    frame = indata[:, 0]
    level = float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))
    detector.detect(frame)
    stats["frames"] += 1
    stats["sum_squares"] += level * level
    stats["max_level"] = max(stats["max_level"], level)
    stats["max_score"] = max(stats["max_score"], detector.last_confidence)


print(
    f"Speak '{phrase}' when the countdown ends. Probe lasts 8 seconds; audio never leaves this machine.",
    flush=True,
)
for number in range(3, 0, -1):
    print(f"{number}...", flush=True)
    time.sleep(1)

with sd.InputStream(
    samplerate=config.sample_rate,
    channels=config.channels,
    blocksize=config.chunk_size,
    dtype="float32",
    callback=on_audio,
):
    for remaining in range(8, 0, -1):
        print(f"Listening locally: {remaining}s", flush=True)
        time.sleep(1)

mean_level = (stats["sum_squares"] / max(stats["frames"], 1)) ** 0.5
peak_db = 20 * np.log10(max(stats["max_level"], 1e-9))
print(f"Average RMS {mean_level:.4f}; peak RMS {stats['max_level']:.4f} ({peak_db:.1f} dBFS)")
print(
    f"Peak {phrase} confidence {stats['max_score']:.3f} "
    f"(activation threshold {config.wakeword_threshold:.3f})",
    flush=True,
)

if stats["max_level"] < 0.005:
    print(
        "VERDICT: MIC IS TOO QUIET. Check Windows mic mute/volume and select the "
        "working input device; wake cannot work from this signal.",
        flush=True,
    )
elif stats["max_score"] >= config.wakeword_threshold:
    print("VERDICT: GOOD. The wake phrase should have triggered.", flush=True)
else:
    suggested = max(0.02, round(stats["max_score"] * 0.8, 3))
    print(
        f"VERDICT: Mic heard you, but threshold is too high. "
        f"Use -Threshold {suggested}.",
        flush=True,
    )
