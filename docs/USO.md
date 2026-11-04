# Conectar outro aparelho

As instruções pressupõem que KNULLI Cast já esteja instalado no RG35XX SP.

## Antes de começar

1. Ligue o RG35XX SP e deixe a tampa aberta.
2. Conecte o portátil e o receptor à mesma rede local. Confira o IP do portátil em **Start → Configurações de rede**. O endereço pode mudar depois de reiniciar ou trocar de rede; [referência KNULLI](https://knulli.org/configure/networking/).
3. Abra o modo desejado em **Ports** antes de abrir a conexão no receptor.

## Computador: navegador

1. No portátil, escolha **Navegador - Transmitir tela**.
2. No computador, abra `http://IP-DO-PORTATIL:8088` no navegador. Substitua `IP-DO-PORTATIL` pelo endereço que o portátil mostra.
3. Clique em **Assistir**. Mantenha **Transmitir som** marcado; se aparecer **Ativar som**, clique nele.
4. Abra o jogo no portátil e controle por ele.
5. No computador, clique em **Tela cheia** se quiser ampliar a imagem.

## Celular ou tablet Android: navegador

Siga os mesmos passos do computador. Digite o endereço completo na barra do navegador. Se o navegador não permitir áudio ou WebRTC, teste outro navegador compatível ou use Moonlight.

## Computador ou Android: Moonlight

1. Baixe o aplicativo pelas opções do [site oficial](https://moonlight-stream.org/). Para Android, o site aponta para a [Google Play](https://play.google.com/store/apps/details?id=com.limelight).
2. No portátil, abra **Moonlight - Transmitir tela** e deixe a tela de pareamento aberta.
3. No aplicativo do receptor, use a opção de adicionar um computador e informe o IP do portátil. Aqui não se usa a porta `8088`.
4. Selecione **KNULLI RG35XX SP**. Caso apareça um PIN no receptor, digite-o no portátil e confirme com **A**.
5. Abra **Tela do KNULLI** no Moonlight. Ao iniciar a transmissão, a tela de pareamento fecha para permitir que você escolha um jogo no portátil.
6. Em conexões futuras, selecione o mesmo aparelho e a mesma tela; não é necessário parear novamente enquanto os dados forem preservados.

Para Mac, a configuração testada foi 640 × 480, 60 FPS, 3 Mbps e H.264. Para Android/TV, comece pela resolução oferecida mais próxima, como 720p/60, e teste. Os nomes dos botões variam entre versões do Moonlight.

## Qualidade no próprio RG35XX SP

Para o modo Moonlight, abra **Ports → Moonlight - Ajustes**. Cima/baixo escolhem a opção; esquerda/direita alteram. A também percorre as opções. Termine em **Salvar e aplicar**. Se o transmissor estiver ligado, confirme a reinicialização e reconecte o Moonlight do receptor.

Comece com **Equilibrado**. Para priorizar menos dados e processamento, teste **Mais rápido**; se a rede estiver instável, teste **Rede fraca**. **Mais qualidade** usa menos compressão, exigindo uma conexão melhor. Os limites e valores de cada perfil estão no [README](../README.md#ajustar-a-transmissão-no-próprio-portátil).

O número em ms representa o buffer solicitado para a captura do som. Ele não mede o atraso total até o alto-falante. A resolução continua nas configurações do Moonlight do receptor; um limite menor definido no receptor também prevalece sobre o do portátil.

## TV ou projetor

**Com Android e loja de aplicativos:** instale Moonlight, se estiver disponível para o aparelho, e siga o pareamento acima. Um navegador com suporte suficiente também pode abrir o modo navegador.

**Com Android, mas sem loja:** a disponibilidade de navegador ou aplicativo depende do sistema do fabricante. Use os canais oficiais de distribuição do Moonlight indicados no site do projeto.

**Sem Android ou sem navegador compatível:** conecte um computador ou receptor compatível por HDMI à TV/projetor. O computador ou receptor é quem recebe a transmissão do RG35XX SP.

Esses destinos ainda não foram testados com este transmissor; a existência de um cliente Moonlight não comprova compatibilidade deste protótipo com todos eles.

## Parar e retomar

- **Parar** no navegador desconecta aquela reprodução.
- Fechar a janela de transmissão do Moonlight desconecta aquele receptor.
- **Ports → Parar transmissão** encerra os serviços no portátil.
- Depois de reiniciar o portátil, abra novamente o atalho do modo desejado.
- Se o portátil dormir, acorde-o e reconecte no receptor.

## Se algo falhar

| Situação | O que conferir |
| --- | --- |
| O endereço não abre | Portátil acordado, IP atual e modo navegador iniciado |
| A página abre, mas não há vídeo | Pressionar Assistir, compatibilidade WebRTC/H.264 e comunicação permitida entre os aparelhos na rede |
| Sem som | Transmitir som marcado, volume do receptor e botão Ativar som, se aparecer |
| Moonlight não encontra o portátil | Iniciar o modo Moonlight e adicionar o IP manualmente, sem `:8088` |
| O PIN não aparece no portátil | O PIN é exibido primeiro no receptor; a tela do portátil permite digitá-lo |
| Duas versões do som parecem ecoar | Ouvir apenas um dos aparelhos ajuda a avaliar a transmissão; o som do portátil e o do receptor percorrem caminhos diferentes |

Para comparar atraso, prefira os alto-falantes do receptor ou um fone com fio durante o teste. Registre o modelo e a versão do receptor ao informar resultados.
