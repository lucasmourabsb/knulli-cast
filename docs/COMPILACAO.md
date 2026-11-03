# Compilar o servidor Moonlight

O executável usado no teste foi compilado em um Mac Apple Silicon com Rust 1.99.1, Zig 0.14.1, destino `aarch64-unknown-linux-gnu` e glibc-alvo 2.31. O servidor usa a `libopus.so.0` do KNULLI (1.4 no aparelho testado).

## Pré-requisitos no computador

- Python 3.9 ou posterior no computador que preparará as fontes.
- Rust/Cargo e o destino `aarch64-unknown-linux-gnu` instalados.
- Zig no PATH ou na variável `ZIG`.
- CMake e as ferramentas de compilação do computador no PATH.
- Uma cópia local da biblioteca ARM64 `libopus.so.0` do KNULLI, com o nome `libopus.so`, em uma pasta de sysroot. Não use a biblioteca x86/Apple do computador.

Os wrappers em `tools/` reproduzem a adaptação de target usada no build original. O driver em `scripts/build-native.py` configura as variáveis de compilação; esta organização dos scripts é nova e deve ser conferida no ambiente de quem for recompilar.

```sh
rustup target add aarch64-unknown-linux-gnu
export OPUS_LIB_DIR="/caminho/para/sysroot/lib"
export ZIG="/caminho/para/zig"
python3 scripts/build-native.py
```

O script confere o arquivo completo de fontes em `native/rgsp-cast-knulli-source.tar.gz`, extrai em `native/source/`, compila apenas `rgsp-host`, preserva o Cargo.lock e copia o resultado para `handheld/moonlight-host`. O instalador e os hooks NextUI do projeto original não são usados nesta adaptação.

O wrapper remove `--fix-cortex-a53-843419`, conforme a correção discutida em [cargo-zigbuild #452](https://github.com/rust-cross/cargo-zigbuild/pull/452), e mapeia o alvo do Rust para `aarch64-linux-gnu.2.31` no Zig.

## Verificar a biblioteca de captura

```sh
python3 scripts/prepare_native.py
cd native/source
cargo test -p rgsp-cedar --lib
```

Os 39 testes dessa biblioteca passaram durante o desenvolvimento. Os testes que dependem de framebuffer, CedarC ou áudio do portátil precisam do hardware correspondente.

## Verificar os scripts

```sh
python3 -m compileall -q handheld scripts tools
node tests/audio-queue.cjs
```

## Ambiente de execução no KNULLI

Os atalhos e `moonlightctl.py` configuram estes caminhos ao iniciar:

```text
LD_LIBRARY_PATH=/userdata/system/knulli-cast/lib
RGSP_USERDATA=/userdata/system/knulli-cast
RGSP_RUN_DIR=/tmp/knulli-moonlight
XDG_DATA_HOME=/userdata/system/knulli-cast/moonlight-state
```

Não copie as chaves e os pareamentos de um aparelho para o repositório.
