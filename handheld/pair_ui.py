#!/usr/bin/env python3
"""PIN entry on the handheld, using its D-pad and A/B buttons."""
import os
import queue
import socket
import sys
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path
import moonlightctl


INPUT_CONFIGS = (
    Path('/userdata/system/configs/emulationstation/es_input.cfg'),
    Path('/usr/share/emulationstation/es_input.cfg'),
)


def button_actions(name, guid, paths=INPUT_CONFIGS):
    """Use the controller's KNULLI mapping instead of assuming A is button 0."""
    best, best_score = None, -1
    for path in paths:
        try:
            configs = ET.parse(path).getroot().iter('inputConfig')
            for config in configs:
                same_guid = bool(guid) and config.get('deviceGUID', '').lower() == guid.lower()
                same_name = config.get('deviceName', '').casefold() == name.casefold()
                score = 3 if same_guid and same_name else 2 if same_guid else 1 if same_name else 0
                if not score or score <= best_score:
                    continue
                bindings = {}
                for entry in config.findall('input'):
                    action = {'a': 'ok', 'b': 'back', 'start': 'ok'}.get(entry.get('name'))
                    if action and entry.get('type') == 'button':
                        try:
                            bindings[int(entry.get('id'))] = action
                        except (TypeError, ValueError):
                            continue
                if 'ok' in bindings.values() and 'back' in bindings.values():
                    best, best_score = bindings, score
        except (OSError, ET.ParseError):
            continue
    return best if best is not None else {0: 'ok', 1: 'back'}


def main():
    preview = '--preview' in sys.argv or '--preview-idle' in sys.argv
    os.environ.setdefault('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')
    if preview:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
    else:
        moonlightctl.start()
    import pygame
    if preview:
        pygame.font.init()
        screen = pygame.Surface((640,480))
        joysticks = {}
    else:
        pygame.init()
        screen = pygame.display.set_mode((640,480),pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        pygame.joystick.init()
        joysticks = {}
    mappings = {}

    def add_joystick(index):
        joystick = pygame.joystick.Joystick(index)
        joystick.init()
        instance = joystick.get_instance_id()
        joysticks[instance] = joystick
        mappings[instance] = button_actions(joystick.get_name(), joystick.get_guid())

    if not preview:
        for index in range(pygame.joystick.get_count()):
            add_joystick(index)
    fonts = {size:pygame.font.Font(None,size) for size in [21,25,29,36,48,62]}
    green, white, gray = (201,239,137), (244,245,237), (155,169,159)
    inbox = queue.Queue()
    ended = threading.Event()
    state = {'pending':[], 'paired':[]}
    digits, position, selected = [0,0,0,0], 0, 0
    editing = False
    busy = False
    notice = ''
    success_until = 0
    seen_pending = None

    def poll():
        while not ended.is_set():
            try:
                inbox.put(('state', moonlightctl.status()))
            except (OSError, ValueError, RuntimeError):
                pass
            ended.wait(.6)

    def submit(client_id, code):
        try:
            inbox.put(('paired', moonlightctl.pair(client_id, code)))
        except (OSError, ValueError, RuntimeError) as error:
            inbox.put(('error', str(error)))

    if not preview:
        threading.Thread(target=poll, daemon=True).start()
    elif '--preview-idle' not in sys.argv:
        state['pending'] = [{'id':'preview','address':'Televisão'}]
        editing = True

    def text(value, size, y, color=white, x=32, centered=False):
        image = fonts[size].render(value, True, color)
        if centered:
            x = (640-image.get_width())//2
        screen.blit(image,(x,y))

    def hints():
        # The bundled font lacks arrow glyphs; draw these icons directly.
        groups = [('horizontal', 'Escolher'), ('vertical', 'Alterar'),
                  ('A', 'Confirmar'), ('B', 'Voltar')]
        gap = 24
        widths = [(40 if icon in ('horizontal', 'vertical') else 22)
                  + 7 + fonts[21].size(label)[0] for icon, label in groups]
        x = (640 - sum(widths) - gap * (len(groups)-1)) // 2
        y = 448

        def arrow(cx, cy, direction):
            dx, dy = direction
            tip = (cx+7*dx, cy+7*dy)
            tail = (cx-6*dx, cy-6*dy)
            base = (cx+dx, cy+dy)
            pygame.draw.line(screen, gray, tail, base, 2)
            pygame.draw.polygon(screen, gray,
                                [tip, (base[0]-5*dy, base[1]+5*dx),
                                 (base[0]+5*dy, base[1]-5*dx)])

        for (icon, label), width in zip(groups, widths):
            if icon in ('horizontal', 'vertical'):
                directions = [(-1,0), (1,0)] if icon == 'horizontal' else [(0,-1), (0,1)]
                for offset, direction in zip((9, 29), directions):
                    arrow(x+offset, y, direction)
                icon_width = 40
            else:
                pygame.draw.circle(screen, gray, (x+10,y), 10, 1)
                glyph = fonts[21].render(icon, True, white)
                screen.blit(glyph, glyph.get_rect(center=(x+10,y)))
                icon_width = 22
            text(label,21,440,gray,x=x+icon_width+7)
            x += width + gap

    clock = pygame.time.Clock()
    try:
        while not ended.is_set():
            while not inbox.empty():
                kind, value = inbox.get_nowait()
                if kind == 'state':
                    state = value
                    if state.get('casting'):
                        ended.set()
                    selected = min(selected,max(0,len(state['pending'])-1))
                    if len(state['pending'])==1 and state['pending'][0]['id']!=seen_pending:
                        seen_pending = state['pending'][0]['id']
                        editing = True
                    elif not state['pending']:
                        seen_pending = None
                        editing = False
                elif kind == 'paired':
                    busy = False
                    if value:
                        notice = 'Pareado! Selecione Tela do KNULLI no receptor.'
                        success_until = time.monotonic()+3
                    else:
                        notice = 'PIN não aceito. Confira os números e tente de novo.'
                elif kind == 'error':
                    busy = False
                    notice = value[:66]
            for event in ([] if preview else pygame.event.get()):
                action = None
                if event.type == pygame.QUIT:
                    ended.set()
                elif event.type == pygame.JOYDEVICEADDED:
                    add_joystick(event.device_index)
                elif event.type == pygame.JOYDEVICEREMOVED:
                    joysticks.pop(event.instance_id, None)
                    mappings.pop(event.instance_id, None)
                elif event.type == pygame.KEYDOWN:
                    action = {pygame.K_LEFT:'left',pygame.K_RIGHT:'right',pygame.K_UP:'up',
                              pygame.K_DOWN:'down',pygame.K_RETURN:'ok',pygame.K_ESCAPE:'back',
                              pygame.K_a:'ok',pygame.K_b:'back'}.get(event.key)
                elif event.type == pygame.JOYHATMOTION:
                    x,y = event.value
                    action = 'right' if x>0 else 'left' if x<0 else 'up' if y>0 else 'down' if y<0 else None
                elif event.type == pygame.JOYBUTTONDOWN:
                    action = mappings.get(event.instance_id, {}).get(event.button)
                if busy or success_until:
                    continue
                pending = state['pending']
                if action == 'back':
                    if editing:
                        editing = False
                    else:
                        ended.set()
                elif pending and editing:
                    if action == 'left': position=(position-1)%4
                    elif action == 'right': position=(position+1)%4
                    elif action == 'up': digits[position]=(digits[position]+1)%10
                    elif action == 'down': digits[position]=(digits[position]-1)%10
                    elif action == 'ok':
                        busy = True
                        notice = 'Pareando…'
                        threading.Thread(target=submit,args=(pending[selected]['id'],''.join(map(str,digits))),daemon=True).start()
                elif pending:
                    if action in ('up','down'):
                        selected=(selected+(-1 if action=='up' else 1))%len(pending)
                    elif action=='ok':
                        editing = True
                        notice = ''
            screen.fill((16,19,19))
            text('KNULLI  ·  MOONLIGHT',25,28,green)
            text('Transmitir a tela',48,68)
            if success_until:
                text('Pareado!',62,178,green,centered=True)
                text('Selecione Tela do KNULLI no Moonlight.',29,265,centered=True)
                if time.monotonic()>=success_until: ended.set()
            elif state['pending'] and editing:
                text('Digite o PIN mostrado no outro aparelho.',29,136)
                for i,value in enumerate(digits):
                    rectangle=pygame.Rect(148+i*88,202,76,84)
                    pygame.draw.rect(screen,(39,48,42),rectangle,border_radius=10)
                    if i==position:pygame.draw.rect(screen,green,rectangle,3,border_radius=10)
                    image=fonts[62].render(str(value),True,green if i==position else white)
                    screen.blit(image,image.get_rect(center=rectangle.center))
                text(notice or 'A confirma o PIN. B volta.',25,322,gray,centered=True)
            elif state['pending']:
                text('Escolha o receptor e pressione A.',29,142)
                for i,client in enumerate(state['pending'][:5]):
                    label=client.get('name') or client.get('address') or 'Moonlight'
                    text(('› ' if i==selected else '  ')+label,29,195+i*35,green if i==selected else gray)
            else:
                text('1. Abra o Moonlight no outro aparelho.',29,154)
                text('2. Adicione o portátil pelo endereço:',29,200)
                try:
                    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                        sock.connect(('192.168.0.1',9)); address=sock.getsockname()[0]
                except OSError:address='Consulte os ajustes de rede'
                text(address,36,243,green)
                text('3. Selecione KNULLI RG35XX SP.',29,296)
                text('Receptor já pareado? Abra Tela do KNULLI por lá.' if state['paired'] else 'Esperando o outro aparelho…',25,351,gray)
            hints()
            if not preview:
                pygame.display.flip()
            if preview:
                pygame.image.save(screen,'/tmp/knulli-moonlight-pair-preview.png')
                ended.set()
            clock.tick(30)
    finally:
        ended.set()
        pygame.quit()


if __name__ == '__main__':
    main()
