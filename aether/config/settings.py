import os
from dataclasses import dataclass, field
from pathlib import Path

# Load the repo .env before reading environment-backed fields below.
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parents[2] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:  # pragma: no cover - dotenv is optional for library use
    pass


from aether.secret_store import secret


@dataclass
class AETHERConfig:
    # API
    gemini_api_key: str = field(default_factory=lambda: secret("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")), repr=False)
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    use_gemini_live: bool = os.getenv("USE_GEMINI_LIVE", "true").lower() == "true"

    # Realtime voice (Gemini Live)
    gemini_live_model: str = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-live")
    gemini_live_voice: str = os.getenv("GEMINI_LIVE_VOICE", "Aoede")
    live_output_sample_rate: int = int(os.getenv("GEMINI_LIVE_OUTPUT_RATE", "24000"))
    # Seconds of silence after the last exchange before AETHER returns to sleep.
    awake_timeout_seconds: float = float(os.getenv("AETHER_AWAKE_TIMEOUT", "20"))
    # Local voice tools (open apps, volume, screenshot, ...) exposed to the model.
    voice_tools_enabled: bool = os.getenv("AETHER_VOICE_TOOLS", "true").lower() == "true"


    # Wake word. The model name must match a key exposed by the loaded
    # openWakeWord model (for example "hey_jarvis", "alexa", "hey_mycroft").
    # "aether" is not a bundled openWakeWord model, so it can never match.
    wakeword_enabled: bool = os.getenv("AETHER_WAKEWORD_ENABLED", "true").lower() == "true"
    wakeword_model: str = os.getenv("AETHER_WAKEWORD_MODEL", "hey_jarvis")
    wakeword_threshold: float = float(os.getenv("AETHER_WAKEWORD_THRESHOLD", "0.5"))
    wakeword_models_dir: Path = Path(os.getenv("AETHER_WAKEWORD_MODELS_DIR", "aether/models/wakeword"))

    # VAD
    vad_enabled: bool = True
    vad_aggressiveness: int = 2  # 0-3
    vad_frame_duration_ms: int = 30
    vad_padding_duration_ms: int = 300

    # Audio
    audio_input_device: int = None
    audio_output_device: int = None
    sample_rate: int = 16000
    channels: int = 1
    # 30 ms at 16 kHz is 480 samples, which WebRTC VAD accepts.
    chunk_size: int = 480

    # TTS
    tts_engine: str = "browser"  # browser, piper, gtts (legacy browser/web path)
    tts_voice: str = "en-US-AriaNeural"
    # Shared speech backends (aether.core.voice.speech): local-first by default.
    # AETHER_TTS_BACKEND: "local" (default), "elevenlabs", or a comma list like
    # "elevenlabs,local". ElevenLabs needs BOTH of these (two different values):
    elevenlabs_api_key: str = field(default_factory=lambda: secret("ELEVENLABS_API_KEY", os.getenv("ELEVENLABS_API_KEY", "")), repr=False)
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    elevenlabs_model: str = os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2")

    # STT
    stt_engine: str = "gemini"  # gemini, whisper, vosk

    # System control
    system_control_enabled: bool = True
    require_confirmation: bool = True
    allowed_apps: list[str] = field(default_factory=lambda: [
        "chrome.exe", "msedge.exe", "firefox.exe", "notepad.exe",
        "code.exe", "devenv.exe", "explorer.exe", "calc.exe"
    ])
    allowed_domains: list[str] = field(default_factory=lambda: [
        "google.com", "github.com", "stackoverflow.com", "youtube.com"
    ])

    # Memory
    memory_enabled: bool = True
    memory_path: Path = Path("data/memory/chroma")
    embedding_model: str = "all-MiniLM-L6-v2"

    # Proactivity
    proactivity_enabled: bool = True
    context_monitoring: bool = True
    proactive_suggestions: bool = True

    # UI
    overlay_enabled: bool = True
    overlay_always_on_top: bool = True
    hotkey_summon: str = "win+shift+j"

    # Privacy
    local_only: bool = False  # if True, avoid cloud where possible
    log_audio: bool = False


config = AETHERConfig()
