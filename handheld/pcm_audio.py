"""Small, same-origin PCM stream for interactive Web Audio playback."""
import os
import re
import socket
import subprocess
import threading
import time

MONITOR = 'alsa_output._sys_devices_platform_soc_soc_03000000_codec_mach_sound_card0.stereo-fallback.monitor'
slots = threading.BoundedSemaphore(3)
lock = threading.Lock()
children = {}
stopping = threading.Event()


def serve(handler):
    if handler.headers.get('Origin') not in (None, 'http://' + handler.headers.get('Host', '')):
        return handler.reply(403, b'Origem nao permitida.')
    token = handler.headers.get('X-Cast-Audio', '')
    if not re.fullmatch('[a-f0-9]{32}', token):
        return handler.reply(400, b'Sessao de som invalida.')
    if stopping.is_set() or not slots.acquire(blocking=False):
        return handler.reply(503, b'Tente conectar novamente.')
    process = None
    try:
        env = os.environ.copy()
        env['PULSE_RUNTIME_PATH'] = '/var/run/pulse'
        env['PULSE_LATENCY_MSEC'] = '5'
        command = [
            '/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin',
            '-probesize', '32', '-analyzeduration', '1', '-f', 'pulse',
            '-fragment_size', '960', '-sample_rate', '48000', '-channels', '2',
            '-i', MONITOR, '-vn', '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2',
            '-flush_packets', '1', '-f', 's16le', 'pipe:1',
        ]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, env=env)
        with lock:
            if stopping.is_set():
                return
            if token in children:
                return handler.reply(409, b'Sessao de som ja aberta.')
            children[token] = (process, time.monotonic() + 15)
        # HTTP/1.0 close-delimited streaming: no browser media-player buffer.
        handler.close_connection = True
        handler.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        handler.connection.settimeout(2)
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/octet-stream')
        handler.send_header('Cache-Control', 'no-store, no-transform')
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.send_header('Connection', 'close')
        handler.end_headers()
        while not stopping.is_set():
            with lock:
                session = children.get(token)
            if not session or time.monotonic() > session[1]:
                break
            block = process.stdout.read(960)
            if not block:
                break
            handler.wfile.write(block)
            handler.wfile.flush()
    except (OSError, ConnectionError):
        pass
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()
            with lock:
                if children.get(token, (None,))[0] is process:
                    children.pop(token, None)
        slots.release()


def keep_alive(token, stop=False):
    with lock:
        session = children.get(token)
        if session and not stop:
            children[token] = (session[0], time.monotonic() + 15)
    if session and stop:
        session[0].terminate()


def shutdown():
    stopping.set()
    with lock:
        active = tuple(item[0] for item in children.values())
    for process in active:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
