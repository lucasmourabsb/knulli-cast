#!/usr/bin/env python3
"""Start, stop and pair the KNULLI Moonlight host through its local socket."""
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN = Path('/tmp/knulli-moonlight')
LOG = Path('/tmp/knulli-moonlight.log')


def pid():
    try:
        value = int((RUN/'daemon.pid').read_text())
        if Path(f'/proc/{value}/exe').resolve() == ROOT/'moonlight-host':
            return value
    except (OSError, ValueError):
        pass
    return None


def messages(sock):
    decoder = json.JSONDecoder()
    buffer = ''
    while True:
        data = sock.recv(65536)
        if not data:
            raise ConnectionError('O serviço Moonlight encerrou a conexão.')
        buffer += data.decode()
        while buffer.strip():
            buffer = buffer.lstrip()
            try:
                message, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                break
            buffer = buffer[end:]
            yield message


def status():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(2)
        sock.connect(str(RUN/'control.sock'))
        sock.sendall(b'{"jsonrpc":"2.0","id":1,"method":"state_subscribe","params":[]}\n')
        for message in messages(sock):
            result = message.get('params', {}).get('result')
            if isinstance(result, dict) and 'pending' in result:
                return result
            if 'error' in message:
                raise RuntimeError(message['error']['message'])


def pair(client_id, pin):
    if len(pin) != 4 or not pin.isdigit():
        raise ValueError('Digite os quatro números mostrados pelo Moonlight.')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect(str(RUN/'control.sock'))
        request = {'jsonrpc':'2.0', 'id':1, 'method':'submit_pin',
                   'params':{'id':client_id, 'pin':pin}}
        sock.sendall(json.dumps(request).encode()+b'\n')
        for message in messages(sock):
            if message.get('id') == 1:
                if 'error' in message:
                    raise RuntimeError(message['error']['message'])
                return message.get('result', {}).get('paired', False)


def start(keep_web=False):
    if not keep_web:
        subprocess.run([sys.executable, str(ROOT/'server.py'), 'stop'], check=True)
    if pid():
        return
    env = os.environ.copy()
    env.update({'LD_LIBRARY_PATH':str(ROOT/'lib'), 'RGSP_USERDATA':str(ROOT),
                'RGSP_RUN_DIR':str(RUN), 'XDG_DATA_HOME':str(ROOT/'moonlight-state')})
    with LOG.open('ab') as log:
        child = subprocess.Popen([str(ROOT/'moonlight-host')], env=env,
                                 stdin=subprocess.DEVNULL, stdout=log,
                                 stderr=log, start_new_session=True)
    for _ in range(100):
        if child.poll() is not None:
            raise RuntimeError('Não foi possível iniciar o Moonlight. Consulte '+str(LOG))
        try:
            status()
            return
        except (OSError, ValueError):
            time.sleep(.1)
    raise RuntimeError('O serviço Moonlight demorou para iniciar.')


def stop():
    value = pid()
    if not value:
        return
    os.kill(value, signal.SIGTERM)
    for _ in range(100):
        if not pid():
            return
        time.sleep(.1)
    raise RuntimeError('O Moonlight ainda está encerrando a transmissão.')


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv)>1 else 'start'
    if action == 'start':
        start('--keep-web' in sys.argv)
        print('Moonlight pronto. Adicione o IP do portátil no aparelho receptor.')
    elif action == 'stop':
        stop()
        print('Moonlight encerrado.')
    elif action == 'status':
        print(json.dumps(status(), ensure_ascii=False))
    elif action == 'pair':
        current = status()['pending']
        if len(current) != 1:
            raise RuntimeError('Deixe apenas uma solicitação de pareamento aberta.')
        pin = input('PIN mostrado no outro aparelho: ').strip()
        print('Pareado.' if pair(current[0]['id'], pin) else 'PIN não aceito.')
