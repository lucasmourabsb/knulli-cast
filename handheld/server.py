#!/usr/bin/env python3
"""Local viewer gateway. The go2rtc administration interface stays on loopback."""
import http.client
import http.server
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
import pcm_audio

ROOT = Path(__file__).resolve().parent
PID = Path('/tmp/knulli-cast.pid')
LOG = Path('/tmp/knulli-cast.log')
PORT = 8088


def address():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(('192.168.0.1', 9))
        return sock.getsockname()[0]


def existing_pid():
    try:
        pid = int(PID.read_text())
        if str(ROOT / 'server.py').encode() in Path(f'/proc/{pid}/cmdline').read_bytes():
            return pid
    except (OSError, ValueError):
        pass
    return None


class Viewer(http.server.BaseHTTPRequestHandler):
    server_version = 'KnulliCast/0.1'

    def reply(self, code, body, content_type='text/plain; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        paths = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/audio.js': ('audio.js', 'text/javascript; charset=utf-8'),
                 '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                 '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.path == '/health':
            return self.reply(200, b'{"status":"ready"}', 'application/json')
        if self.path == '/audio.pcm':
            return pcm_audio.serve(self)
        if self.path not in paths:
            return self.reply(404, b'Pagina nao encontrada.')
        name, mime = paths[self.path]
        self.reply(200, (ROOT / name).read_bytes(), mime)

    def do_POST(self):
        if self.path in ('/audio-alive', '/audio-stop'):
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.reply(403, b'Origem nao permitida.')
            if self.headers.get('Content-Length') != '32':
                return self.reply(400, b'Sessao de som invalida.')
            token = self.rfile.read(32).decode('ascii', errors='replace')
            if not re.fullmatch('[a-f0-9]{32}', token):
                return self.reply(400, b'Sessao de som invalida.')
            pcm_audio.keep_alive(token, stop=self.path == '/audio-stop')
            return self.reply(204, b'')
        if self.path != '/offer':
            return self.reply(404, b'Pagina nao encontrada.')
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.reply(403, b'Origem nao permitida.')
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            size = 0
        if not 1 <= size <= 65536:
            return self.reply(400, b'Pedido de conexao invalido.')
        body = self.rfile.read(size)
        backend = http.client.HTTPConnection('127.0.0.1', 1984, timeout=20)
        try:
            backend.request('POST', '/api/webrtc?src=handheld', body,
                            {'Content-Type': 'application/sdp'})
            response = backend.getresponse()
            self.reply(response.status, response.read(), 'application/sdp')
        except (OSError, http.client.HTTPException):
            self.reply(502, b'Nao foi possivel iniciar a transmissao. Tente novamente.')
        finally:
            backend.close()


def serve():
    host = address()
    config = {
        'api': {'listen': '127.0.0.1:1984'},
        'rtsp': {'listen': '127.0.0.1:8554'},
        'webrtc': {'listen': f'{host}:8555', 'ice_servers': [],
                   'candidates': [f'{host}:8555'],
                   'filters': {'ips': [host], 'networks': ['udp4', 'tcp4']}},
        'streams': {'handheld': [
            f'exec:/usr/bin/python3 {ROOT}/cedar_capture.py#killsignal=15#killtimeout=4',
            'exec:/usr/bin/ffmpeg -hide_banner -loglevel warning -nostdin '
            '-probesize 32 -analyzeduration 1 -f pulse -fragment_size 1920 '
            '-i alsa_output._sys_devices_platform_soc_soc_03000000_codec_mach_sound_card0.stereo-fallback.monitor '
            '-vn -c:a libopus -compression_level 0 -application lowdelay -frame_duration 10 '
            '-ar 48000 -ac 2 -b:a 64k -flush_packets 1 -muxdelay 0 -max_delay 0 '
            '-rtsp_transport tcp -f rtsp {output}'
        ]},
        'exec': {'allow_paths': ['/usr/bin/python3', '/usr/bin/ffmpeg']},
        'log': {'level': 'info'},
    }
    config_path = Path('/tmp/knulli-cast.json')
    config_path.write_text(json.dumps(config))
    env = os.environ.copy()
    env['PULSE_RUNTIME_PATH'] = '/var/run/pulse'
    env['PULSE_LATENCY_MSEC'] = '10'
    service = subprocess.Popen([str(ROOT / 'go2rtc'), '-config', str(config_path)], env=env)
    shutdown = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: shutdown.set())
    signal.signal(signal.SIGINT, lambda *_: shutdown.set())
    httpd = None
    try:
        httpd = http.server.ThreadingHTTPServer((host, PORT), Viewer)
        httpd.daemon_threads = True
        PID.write_text(str(os.getpid()))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        print(f'Pronto: http://{host}:{PORT}', flush=True)
        while not shutdown.wait(1):
            if service.poll() is not None:
                raise RuntimeError('O serviço de transmissão foi encerrado.')
    finally:
        pcm_audio.shutdown()
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        service.terminate()
        try:
            service.wait(timeout=5)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait()
        if PID.exists() and PID.read_text() == str(os.getpid()):
            PID.unlink()


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else 'start'
    pid = existing_pid()
    if action == 'stop':
        if pid:
            os.kill(pid, signal.SIGTERM)
            for _ in range(60):
                if existing_pid() is None:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('O serviço ainda está encerrando. Tente novamente.')
        print('Transmissão encerrada.')
    elif action == 'serve':
        serve()
    elif pid:
        print(f'Transmissão disponível: http://{address()}:{PORT}')
    else:
        with LOG.open('ab') as log:
            process = subprocess.Popen([sys.executable, str(ROOT / 'server.py'), 'serve'],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True)
        for _ in range(30):
            if process.poll() is not None:
                raise RuntimeError(f'Falha ao iniciar. Consulte {LOG}.')
            if existing_pid():
                print(f'Transmissão disponível: http://{address()}:{PORT}')
                return
            time.sleep(0.1)
        raise RuntimeError('O serviço demorou para iniciar.')


if __name__ == '__main__':
    main()
