#!/usr/bin/env python3
"""Moonlight quality controls on the handheld, without changing the games."""
import os
import queue
import sys
import threading
import time
import moonlightctl
import stream_settings as preferences
from pair_ui import button_actions


def main():
    preview = '--preview' in sys.argv or '--preview-fast' in sys.argv
    os.environ.setdefault('SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')
    if preview:
        os.environ.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    import pygame
    if preview:
        pygame.font.init()
        screen = pygame.Surface((640, 480))
    else:
        pygame.init()
        screen = pygame.display.set_mode((640, 480), pygame.FULLSCREEN)
        pygame.mouse.set_visible(False)
        pygame.joystick.init()
    fonts = {n: pygame.font.Font(None, n) for n in (21, 24, 26, 38, 43)}
    green, white, gray = (201, 239, 137), (244, 245, 237), (155, 169, 159)
    initial = preferences.load()
    values = dict(initial)
    if '--preview-fast' in sys.argv:
        values.update(preferences.PROFILES['fast'][1])
    selected, mode, reconnect = 0, 'edit', False
    notice = ''
    ended = threading.Event()
    inbox = queue.Queue()
    joysticks, mappings, axes = {}, {}, {}
    fields = ('profile', 'video_kbps', 'max_fps', 'audio_kbps', 'audio_buffer_ms', 'save')
    labels = ('Perfil', 'Qualidade da imagem', 'Fluidez', 'Qualidade do som',
              'Buffer do som', 'Salvar e aplicar')
    help_text = (
        'Escolha um perfil ou ajuste cada opção abaixo.',
        'Menos Mbps alivia a rede; mais Mbps preserva detalhes.',
        '60 FPS: mais fluidez. 30 FPS: menos dados e trabalho.',
        'Som estéreo. Mais kbps preserva mais detalhes.',
        'Menor buffer reduz espera; aumente se o som cortar.',
        'Salve aqui. Uma transmissão em andamento precisará reconectar.',
    )

    def add_joystick(index):
        joystick = pygame.joystick.Joystick(index)
        joystick.init()
        instance = joystick.get_instance_id()
        joysticks[instance] = joystick
        mappings[instance] = button_actions(joystick.get_name(), joystick.get_guid())

    def save():
        try:
            inbox.put(('saved', moonlightctl.apply_settings(dict(values))))
        except (OSError, RuntimeError, ValueError) as error:
            inbox.put(('error', str(error)))

    def step(direction):
        key = fields[selected]
        if key == 'profile':
            profiles = list(preferences.PROFILES.values())
            name = preferences.profile_name(values)
            current = next((i for i, (label, _) in enumerate(profiles) if label == name), 1)
            values.update(profiles[(current + direction) % len(profiles)][1])
        elif key in preferences.CHOICES:
            options = preferences.CHOICES[key]
            values[key] = options[(options.index(values[key]) + direction) % len(options)]

    def text(value, size, x, y, color=white, right=False, centered=False):
        image = fonts[size].render(value, True, color)
        if right:
            x -= image.get_width()
        if centered:
            x = (640-image.get_width()) // 2
        screen.blit(image, (x, y))

    def paragraph(value, y, color=gray):
        line = ''
        for word in value.split():
            candidate = (line + ' ' + word).strip()
            if line and fonts[21].size(candidate)[0] > 568:
                text(line, 21, 36, y, color)
                y += 23
                line = word
            else:
                line = candidate
        if line:
            text(line, 21, 36, y, color)

    def footer():
        for x, dx, dy in ((40, 0, -1), (60, 0, 1), (166, -1, 0), (186, 1, 0)):
            tip = (x+7*dx, 448+7*dy)
            base = (x+dx, 448+dy)
            pygame.draw.line(screen, gray, (x-6*dx, 448-6*dy), base, 2)
            pygame.draw.polygon(screen, gray, [tip, (base[0]-5*dy, base[1]+5*dx),
                                              (base[0]+5*dy, base[1]-5*dx)])
        text('Mover', 21, 77, 440, gray)
        text('Alterar', 21, 203, 440, gray)
        for x, button, label in ((338, 'A', 'Escolher'), (505, 'B', 'Voltar')):
            pygame.draw.circle(screen, gray, (x, 448), 10, 1)
            glyph = fonts[21].render(button, True, white)
            screen.blit(glyph, glyph.get_rect(center=(x, 448)))
            text(label, 21, x+18, 440, gray)

    if not preview:
        for index in range(pygame.joystick.get_count()):
            add_joystick(index)
    clock = pygame.time.Clock()
    try:
        while not ended.is_set():
            while not inbox.empty():
                kind, value = inbox.get_nowait()
                if kind == 'saved':
                    reconnect, mode = value, 'done'
                elif kind == 'error':
                    notice, mode = value, 'error'
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
                    action = {pygame.K_UP: 'up', pygame.K_DOWN: 'down',
                              pygame.K_LEFT: 'left', pygame.K_RIGHT: 'right',
                              pygame.K_RETURN: 'ok', pygame.K_ESCAPE: 'back',
                              pygame.K_a: 'ok', pygame.K_b: 'back'}.get(event.key)
                elif event.type == pygame.JOYBUTTONDOWN:
                    action = mappings.get(event.instance_id, {}).get(event.button)
                elif event.type == pygame.JOYHATMOTION:
                    x, y = event.value
                    action = 'right' if x > 0 else 'left' if x < 0 else 'up' if y > 0 else 'down' if y < 0 else None
                elif event.type == pygame.JOYAXISMOTION and event.axis in (0, 1):
                    key = (event.instance_id, event.axis)
                    value = 1 if event.value > .65 else -1 if event.value < -.65 else 0
                    if value and value != axes.get(key):
                        action = ('right' if value > 0 else 'left') if event.axis == 0 else ('down' if value > 0 else 'up')
                    axes[key] = value
                if mode == 'saving':
                    continue
                if mode in ('done', 'error'):
                    if action == 'back' or (action == 'ok' and mode == 'done'):
                        ended.set()
                    elif action == 'ok':
                        mode = 'edit'
                    continue
                if mode == 'confirm':
                    if action == 'back':
                        mode = 'edit'
                    elif action == 'ok':
                        mode = 'saving'
                        threading.Thread(target=save).start()
                    continue
                if action == 'back':
                    ended.set()
                elif action in ('up', 'down'):
                    selected = (selected + (1 if action == 'down' else -1)) % len(fields)
                elif action in ('left', 'right'):
                    step(1 if action == 'right' else -1)
                elif action == 'ok':
                    if fields[selected] != 'save':
                        step(1)
                    elif moonlightctl.pid() is not None:
                        mode = 'confirm'
                    else:
                        mode = 'saving'
                        threading.Thread(target=save).start()
            screen.fill((16, 19, 19))
            text('MOONLIGHT  ·  AJUSTES', 24, 32, 25, green)
            text('Qualidade da transmissão', 38, 32, 62)
            if mode == 'edit':
                dirty = values != initial
                text('Alterações ainda não salvas' if dirty else 'Escolha como transmitir para o receptor.',
                     21, 34, 103, green if dirty else gray)
                shown = (preferences.profile_name(values),
                         f"Até {values['video_kbps']/1000:g} Mbps",
                         f"Até {values['max_fps']} FPS", f"Até {values['audio_kbps']} kbps",
                         f"{values['audio_buffer_ms']} ms", '')
                for index, (label, value) in enumerate(zip(labels, shown)):
                    y = 138 + index*34
                    if index == selected:
                        pygame.draw.rect(screen, (39, 48, 42), (24, y-4, 592, 31), border_radius=6)
                        pygame.draw.rect(screen, green, (24, y-4, 592, 31), 1, border_radius=6)
                    text(label, 24, 36, y, green if index == selected else white)
                    text(value, 24, 602, y, green if index == selected else gray, right=True)
                paragraph(help_text[selected], 355)
                text('Resolução: ajuste no Moonlight do receptor.', 21, 36, 405, gray)
            elif mode == 'confirm':
                text('Aplicar e reconectar?', 38, 0, 160, green, centered=True)
                text('O transmissor será reiniciado.', 26, 0, 220, centered=True)
                text('Reconecte se estiver assistindo.', 26, 0, 253, centered=True)
                text('A aplica. B continua ajustando.', 24, 0, 320, gray, centered=True)
            elif mode == 'saving':
                text('Salvando os ajustes...', 38, 0, 205, green, centered=True)
            elif mode == 'done':
                text('Ajustes salvos!', 43, 0, 175, green, centered=True)
                paragraph('Reconecte o Moonlight para usar a nova configuração.' if reconnect
                          else 'Abra Moonlight - Transmitir tela para usar a nova configuração.', 245, white)
                text('A ou B para voltar.', 24, 0, 330, gray, centered=True)
            else:
                text('Não foi possível aplicar', 38, 0, 175, centered=True)
                paragraph(notice, 235)
                text('A para tentar novamente. B para voltar.', 24, 0, 330, gray, centered=True)
            footer()
            if preview:
                pygame.image.save(screen, '/tmp/knulli-moonlight-settings-preview.png')
                ended.set()
            else:
                pygame.display.flip()
            clock.tick(30)
    finally:
        ended.set()
        pygame.quit()


if __name__ == '__main__':
    main()
