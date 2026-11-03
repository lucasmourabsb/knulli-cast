#!/usr/bin/env python3
"""Capture the visible framebuffer page and the existing audio monitor."""
import fcntl
import os
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path

FPS = 30
running = True


def stop(*_):
    global running
    running = False


def geometry(fd):
    data = bytearray(160)
    fcntl.ioctl(fd, 0x4600, data, True)
    return struct.unpack_from('7I', data)


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    fb = os.open('/dev/fb0', os.O_RDONLY)
    width, height, _, _, _, _, bpp = geometry(fb)
    if bpp != 32:
        raise RuntimeError('A captura precisa de uma tela com 32 bits por pixel.')
    stride = int(Path('/sys/class/graphics/fb0/stride').read_text())
    env = os.environ.copy()
    # PipeWire supplies a PulseAudio-compatible monitor; this does not reroute sound.
    env['PULSE_RUNTIME_PATH'] = '/var/run/pulse'
    env['PULSE_LATENCY_MSEC'] = '10'
    monitor = 'alsa_output._sys_devices_platform_soc_soc_03000000_codec_mach_sound_card0.stereo-fallback.monitor'
    command = [
        'ffmpeg', '-hide_banner', '-loglevel', 'warning', '-nostdin',
        '-filter_threads', '1',
        '-thread_queue_size', '1', '-probesize', '32', '-analyzeduration', '1',
        '-use_wallclock_as_timestamps', '1',
        '-f', 'rawvideo', '-pixel_format', 'bgra',
        '-video_size', f'{width}x{height}', '-framerate', str(FPS), '-i', 'pipe:0',
        '-thread_queue_size', '2', '-probesize', '32', '-analyzeduration', '1',
        '-f', 'pulse', '-fragment_size', '1920', '-i', monitor,
        '-map', '0:v:0', '-map', '1:a:0',
        '-vf', 'scale=480:360:flags=fast_bilinear,setsar=1',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
        '-profile:v', 'baseline', '-level:v', '3.1', '-pix_fmt', 'yuv420p',
        '-threads:v', '2', '-crf', '26', '-maxrate', '2000k', '-bufsize', '150k',
        '-g', str(FPS), '-keyint_min', str(FPS), '-bf', '0',
        '-x264-params', 'scenecut=0:repeat-headers=1',
        '-c:a', 'libopus', '-application', 'lowdelay', '-frame_duration', '10',
        '-ar', '48000', '-ac', '2', '-b:a', '64k',
        '-fps_mode', 'passthrough', '-muxdelay', '0', '-max_delay', '0',
        '-max_interleave_delta', '10000', '-flush_packets', '1',
        '-rtsp_transport', 'tcp', '-f', 'rtsp', sys.argv[1],
    ]
    encoder = subprocess.Popen(command, stdin=subprocess.PIPE, bufsize=0, env=env)
    deadline = time.monotonic()
    try:
        while running and encoder.poll() is None:
            current = geometry(fb)
            if current[:2] != (width, height) or current[6] != bpp:
                raise RuntimeError('A resolução mudou. Reconecte a transmissão.')
            # KNULLI flips between two framebuffer pages while drawing.
            offset = current[5] * stride + current[4] * 4
            frame = os.pread(fb, stride * height, offset)
            if len(frame) != stride * height:
                raise RuntimeError('Não foi possível ler um quadro completo.')
            if stride != width * 4:
                frame = b''.join(frame[y * stride:y * stride + width * 4]
                                 for y in range(height))
            view = memoryview(frame)
            while view and running:
                sent = encoder.stdin.write(view)
                if not sent:
                    raise BrokenPipeError('O codificador foi encerrado.')
                view = view[sent:]
            deadline += 1 / FPS
            delay = deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            elif delay < -1 / FPS:
                deadline = time.monotonic()
    except BrokenPipeError:
        pass
    finally:
        os.close(fb)
        encoder.stdin.close()
        if encoder.poll() is None:
            encoder.terminate()
        try:
            encoder.wait(timeout=3)
        except subprocess.TimeoutExpired:
            encoder.kill()
            encoder.wait()


if __name__ == '__main__':
    main()
