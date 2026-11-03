# Arquitetura e verificação

## Transmissor

- O codificador CedarC lê o framebuffer ARM64 do H700 e produz H.264 por hardware.
- A estrutura `VencOutputBuffer` usa os tamanhos e endereços dos dois trechos do buffer circular. Os trechos são reunidos antes de converter AVCC em Annex B.
- A captura de áudio lê o monitor PulseAudio da saída analógica existente; o projeto não instala `snd-aloop` nem redireciona a saída dos jogos.
- O serviço de navegador expõe somente os arquivos da página, a negociação WebRTC e os caminhos de áudio na rede local. A administração go2rtc permanece em loopback.
- O servidor nativo adapta rgsp-cast/moonshine para KNULLI e anuncia **Tela do KNULLI**, uma aplicação sem comando de encerramento do jogo.

## Áudio no navegador

O caminho preferido envia PCM S16LE estéreo, 48 kHz, em blocos de 5 ms por uma resposta HTTP contínua. Um AudioContext com `latencyHint: interactive` consome uma fila curta. Como AudioWorklet depende de contexto seguro, este protótipo usa ScriptProcessor no acesso HTTP local. Essa API é antiga; o caminho Opus/WebRTC permanece disponível como alternativa automática.

A fila começa com uma margem de 32 ms e pode aumentar até 48 ms após uma falta de amostras. Áudio acumulado demais é descartado para não aumentar o atraso continuamente. O serviço limita ouvintes e encerra uma captura que fica 15 segundos sem a confirmação periódica do receptor.

Referências: [Web Audio](https://www.w3.org/TR/webaudio-1.0/), [captura PulseAudio no ffmpeg](https://ffmpeg.org/ffmpeg-devices.html#pulse).

## Resultados observados

- Mac com Moonlight 6.2.0: recepção H.264 640 × 480 em torno de 60 FPS.
- Três passagens pelo fim do buffer circular de vídeo observadas sem os erros de decodificação que ocorriam antes da correção.
- 39 testes da biblioteca de captura passaram.
- Navegador no Mac: medições anteriores de vídeo de aproximadamente 82–106 ms entre captura e imagem. O teste temporário desenhava um código nos quadros transmitidos; essa instrumentação foi removida.
- No ajuste de áudio PCM, a fila observada ficou aproximadamente entre 32 e 56 ms. Esse número não representa a latência até os alto-falantes.
- No teste subjetivo com os alto-falantes do computador, o atraso em relação ao áudio do portátil foi relatado como bem menor após o ajuste.
- Verificações do PCM cobrem sinal e canais, blocos partidos, limite da fila, silêncio durante falta de amostras e recuperação. O serviço foi verificado para origem, formato, limite de ouvintes e encerramento.

## Limites

A latência total de áudio até os alto-falantes e a latência total de comandos até a imagem no Moonlight não foram medidas. Tempos de rede, decodificação, fila de áudio e saída do sistema são parcelas distintas.

Android/TV, Windows/Linux, outros roteadores e outras versões do KNULLI ainda precisam de teste. O mapeamento dos botões da tela pygame de pareamento precisa de validação adicional no aparelho. O pareamento do Mac foi confirmado por controle local durante o desenvolvimento.

Não há suporte implementado para controle remoto pelos botões do receptor. O jogador usa os botões do RG35XX SP.

## Rede local

O modo navegador não tem autenticação própria e foi feito para a rede local de confiança. Não há configuração de exposição à internet ou encaminhamento de portas neste projeto. Os certificados e pares do Moonlight são gerados e armazenados apenas no aparelho.

Os logs ficam em `/tmp/knulli-cast.log` e `/tmp/knulli-moonlight.log`. Remova IPs e dados de pareamento antes de compartilhar logs em uma issue.
