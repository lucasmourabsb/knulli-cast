# Instalar em outro RG35XX SP

Esta é uma instalação manual para quem já usa SSH e transferência de arquivos no KNULLI. A configuração testada foi **RG35XX SP, H700, tela 640 × 480, KNULLI Scarab de 11/05/2026, kernel 4.9.170, ARM64**. Outros modelos e sistemas precisam de adaptação.

## Preparar os arquivos no computador

1. Obtenha o código deste repositório.
2. Execute `python3 scripts/get-go2rtc.py` para obter a versão ARM64 fixada e conferir o SHA-256.
3. Para o modo Moonlight, compile `moonlight-host` seguindo [COMPILACAO.md](COMPILACAO.md). O modo navegador não precisa desse executável.
4. Providencie as bibliotecas CedarC na pasta local `handheld/lib/`. Elas não são distribuídas neste repositório. Após `python3 scripts/prepare_native.py`, o projeto original fornece o extrator `native/source/scripts/extract-vendor-libs.sh` para a imagem de firmware oficial fixada da TrimUI. Ele usa Docker privilegiado e precisa ser revisado e executado por quem está preparando a instalação. A imagem serve como fonte de bibliotecas; não instale o firmware da TrimUI no RG35XX SP.

Bibliotecas usadas no teste: `libVE.so`, `libMemAdapter.so`, `libvencoder.so`, `libvideoengine.so`, `libcdc_base.so`, `libvenc_base.so`, `libvenc_common.so`, `libvenc_h264.so`, `libvenc_h265.so` e `libvenc_jpeg.so`.

No KNULLI, são necessários Python 3, ffmpeg com PulseAudio/PCM/Opus, PipeWire/PulseAudio, `iw` e, para o pareamento pela tela, pygame. O servidor Moonlight também usa a `libopus.so.0` do próprio KNULLI. Esses componentes estavam presentes no aparelho testado.

## Copiar para o portátil

1. Habilite SSH no KNULLI seguindo a [documentação oficial](https://knulli.org/configure/ssh/) e consulte o IP atual.
2. Copie o conteúdo de `handheld/` para `/userdata/system/knulli-cast/` usando SFTP ou outro meio de transferência que já utilize. Preserve a pasta `lib/` e os dados de pareamento ao atualizar uma instalação existente.
3. Copie `scripts/install-menu.py` para a mesma pasta do portátil.
4. Com nenhum jogo aberto, execute no portátil:

```sh
chmod +x /userdata/system/knulli-cast/go2rtc
# Necessário apenas se o servidor Moonlight tiver sido preparado:
chmod +x /userdata/system/knulli-cast/moonlight-host
python3 /userdata/system/knulli-cast/install-menu.py
```

O instalador de menu reinicia o EmulationStation, preserva uma cópia do `gamelist.xml` e dos atalhos próprios anteriores e adiciona os atalhos em **Ports**, incluindo **Moonlight - Ajustes**. Os executáveis de cada modo precisam ter sido preparados antes de usar o respectivo atalho. O script não instala firmware nem adiciona serviço à inicialização.

## Atualizar

Encerre a transmissão em **Ports → Parar transmissão** antes de substituir os arquivos do projeto. Preserve `lib/`, `moonlight-state/` e `rgsp-cast/` para manter as bibliotecas e o pareamento local. Não publique essas pastas nem seus certificados.

Os serviços só são iniciados pelos atalhos. Para parar tudo manualmente:

```sh
python3 /userdata/system/knulli-cast/server.py stop
python3 /userdata/system/knulli-cast/moonlightctl.py stop
```

Depois, siga [USO.md](USO.md).
