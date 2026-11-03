#!/usr/bin/env python3
"""PIN entry on the handheld, using its D-pad and A/B buttons."""
import os
import queue
import socket
import sys
import threading
import time
from pathlib import Path
import moonlightctl


def main():
    preview = '--preview' in sys.argv
    if preview:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
    else:
        moonlightctl.start()
    import pygame
    if preview:
        pygame.font.init()
        screen = pygame.Surface((640,480))
        joysticks = []
    else:
        pygame.init()
        screen = pygame.display.set_mode((640,480),pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        pygame.joystick.init()
        joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    for joystick in joysticks:
        joystick.init()
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
    else:
        state['pending'] = [{'id':'preview','address':'Televisão'}]
        editing = True

    def text(value, size, y, color=white, x=32, centered=False):
        image = fonts[size].render(value, True, color)
        if centered:
            x = (640-image.get_width())//2
        screen.blit(image,(x,y))

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
                elif event.type == pygame.KEYDOWN:
                    action = {pygame.K_LEFT:'left',pygame.K_RIGHT:'right',pygame.K_UP:'up',
                              pygame.K_DOWN:'down',pygame.K_RETURN:'ok',pygame.K_ESCAPE:'back',
                              pygame.K_a:'ok',pygame.K_b:'back'}.get(event.key)
                elif event.type == pygame.JOYHATMOTION:
                    x,y = event.value
                    action = 'right' if x>0 else 'left' if x<0 else 'up' if y>0 else 'down' if y<0 else None
                elif event.type == pygame.JOYBUTTONDOWN:
                    action = 'ok' if event.button==0 else 'back' if event.button==1 else None
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
            text('← → Escolher   ↑ ↓ Alterar   A Confirmar   B Voltar',21,440,gray,centered=True)
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
