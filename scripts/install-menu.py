from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET

root = Path('/userdata/system/knulli-cast')
ports = Path('/userdata/roms/ports')
gamelist = ports/'gamelist.xml'
if subprocess.check_output(['/usr/bin/knulli-es-swissknife','--emupid'],text=True).strip() != '0':
    raise SystemExit('Um jogo está aberto. Os atalhos aguardam a atualização do menu.')
entries = [
    ('Transmitir-Moonlight.sh','Transmitir tela - Moonlight.sh','Moonlight - Transmitir tela',
     'Envia a imagem e o som do RG35XX SP para o Moonlight no computador, Android ou televisão. Use o direcional e A para digitar o PIN. Ao iniciar a transmissão, o menu volta automaticamente para você escolher um jogo.'),
    ('Transmitir-Navegador.sh','Transmitir tela - navegador.sh','Navegador - Transmitir tela',
     'Abra o endereço IP do portátil, seguido de :8088, no navegador do outro aparelho. Pressione Assistir e continue jogando no RG35XX SP.'),
    ('Parar-transmissao.sh','Parar transmissao.sh','Parar transmissão',
     'Encerra os transmissores Moonlight e navegador.'),
]
backup = root/'backup-menu'/str(time.time_ns())
backup.mkdir(parents=True,exist_ok=True)
subprocess.run(['/etc/init.d/S31emulationstation','resume'],
               stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
subprocess.run(['/etc/init.d/S31emulationstation','stop'],
               stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
if subprocess.run(['pidof','emulationstation'],stdout=subprocess.DEVNULL).returncode==0:
    raise SystemExit('O menu ainda está ativo; nenhum arquivo da lista de jogos foi alterado.')
try:
    for old in ['KNULLI Cast - Ligar.sh','KNULLI Cast - Desligar.sh']:
        file = ports/old
        if file.exists():
            shutil.move(str(file),str(backup/file.name))
    raw = gamelist.read_bytes() if gamelist.exists() else b'<?xml version="1.0"?>\n<gameList>\n</gameList>\n'
    if gamelist.exists(): shutil.copyfile(gamelist,backup/'gamelist.xml')
    xml = ET.fromstring(raw)
    existing = {(game.findtext('path') or '').removeprefix('./') for game in xml.findall('game')}
    additions = []
    for source,filename,name,description in entries:
        destination = ports/filename
        if destination.exists():shutil.copyfile(destination,backup/filename)
        shutil.copyfile(root/source,destination)
        destination.chmod(0o755)
        if filename not in existing:
            game = ET.Element('game')
            ET.SubElement(game,'path').text='./'+filename
            ET.SubElement(game,'name').text=name
            ET.SubElement(game,'desc').text=description
            additions.append(ET.tostring(game,encoding='utf-8'))
    if additions:
        end=raw.rfind(b'</gameList>')
        if end<0:raise RuntimeError('Estrutura inesperada da lista de jogos.')
        updated=raw[:end]+b'\n'.join(additions)+b'\n'+raw[end:]
        ET.fromstring(updated)
        temporary=gamelist.with_suffix('.xml.knulli-cast-tmp')
        temporary.write_bytes(updated)
        temporary.replace(gamelist)
    print('Atalhos adicionados ao menu Ports:',len(additions))
finally:
    subprocess.run(['/etc/init.d/S31emulationstation','start'],check=True,
                   stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
