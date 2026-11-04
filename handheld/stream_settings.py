"""Validated, persistent Moonlight transmission preferences."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / 'stream-settings.json'
CHOICES = {
    'video_kbps': (750, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000),
    'max_fps': (30, 60),
    'audio_kbps': (64, 96, 128, 160, 192),
    'audio_buffer_ms': (5, 10, 20),
    'audio_complexity': (1, 3, 5),
}
PROFILES = {
    'fast': ('Mais rápido', dict(video_kbps=1500, max_fps=60, audio_kbps=64,
                              audio_buffer_ms=5, audio_complexity=1)),
    'balanced': ('Equilibrado', dict(video_kbps=3000, max_fps=60, audio_kbps=96,
                                  audio_buffer_ms=5, audio_complexity=3)),
    'quality': ('Mais qualidade', dict(video_kbps=5000, max_fps=60, audio_kbps=192,
                                     audio_buffer_ms=5, audio_complexity=5)),
    'weak': ('Rede fraca', dict(video_kbps=1000, max_fps=30, audio_kbps=64,
                             audio_buffer_ms=10, audio_complexity=1)),
}


def defaults():
    return {'version': 1, **PROFILES['balanced'][1]}


def validate(value):
    if not isinstance(value, dict) or value.get('version', 1) != 1:
        raise ValueError('Formato de ajustes inválido.')
    result = defaults()
    for key, choices in CHOICES.items():
        item = value.get(key, result[key])
        if type(item) is not int or item not in choices:
            raise ValueError('Valor de ajuste inválido: ' + key)
        result[key] = item
    return result


def load(path=SETTINGS):
    try:
        return validate(json.loads(Path(path).read_text()))
    except (OSError, ValueError, TypeError):
        return defaults()


def save(value, path=SETTINGS):
    value = validate(value)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return value


def profile_name(value):
    for name, settings in PROFILES.values():
        if all(value.get(key) == item for key, item in settings.items()):
            return name
    return 'Personalizado'


def fingerprint(value):
    return hashlib.sha256(json.dumps(validate(value), sort_keys=True).encode()).hexdigest()


def environment(value):
    value = validate(value)
    return {
        'RGSP_VIDEO_BITRATE_MAX': str(value['video_kbps'] * 1000),
        'RGSP_VIDEO_FPS_MAX': str(value['max_fps']),
        'RGSP_AUDIO_BITRATE_MAX': str(value['audio_kbps'] * 1000),
        'RGSP_AUDIO_CAPTURE_MS': str(value['audio_buffer_ms']),
        'RGSP_AUDIO_COMPLEXITY': str(value['audio_complexity']),
    }
