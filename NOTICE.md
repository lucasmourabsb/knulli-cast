# Origem e atribuições

- **rgsp-cast**, de codebutler, GPL-3.0: <https://github.com/codebutler/rgsp-cast>. Base usada: commit `2eeb0fa63221a9e72dfc51ea77a01a3be8ff0e1e`. A árvore completa adaptada está em `native/`, com suas licenças e avisos preservados.
- **moonshine-core** e **reth-ipc**: componentes vendorizados da árvore original, preservados em `native/vendor/` com os respectivos avisos.
- **go2rtc**, de AlexxIT, MIT: <https://github.com/AlexxIT/go2rtc/releases/tag/v1.9.15>. O executável não fica no Git; o script de download verifica o SHA-256.
- **CedarC/Allwinner**: interface conferida no [cabeçalho do fabricante](https://github.com/Allwinner-Homlet/H6-CedarC/blob/master/include/vencoder.h). As bibliotecas proprietárias não são incluídas.
- **TrimUI Smart Pro v1.1.1**: [fonte de firmware usada na extração local das bibliotecas](https://github.com/trimui/firmware_smartpro/releases/tag/v1.1.1). O firmware não é incluído nem instalado pelo projeto.
- Avisos das dependências Rust do servidor compilado durante o desenvolvimento: `THIRD-PARTY-LICENSES.txt`.

Mudanças desta adaptação: geometria 640 × 480, monitor de áudio PulseAudio, caminhos e atalhos KNULLI, captura Python, reprodução pelo navegador, fila PCM curta, tela de PIN pygame e correção da leitura dos dois trechos de saída do codificador.

Certificados, chaves, pares, ROMs, BIOS, firmware e bibliotecas proprietárias não fazem parte deste repositório.
