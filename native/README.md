# Fontes do servidor Moonlight para KNULLI

`rgsp-cast-knulli-source.tar.gz` contém a árvore completa adaptada do projeto rgsp-cast, incluindo crates Rust, dependências vendorizadas, fixtures, documentação original e licenças. `SHA256SUMS` registra a soma do arquivo.

`KNULLI.patch` mostra as alterações Rust em relação ao commit original indicado em [NOTICE.md](../NOTICE.md). O arquivo de fontes já contém essas alterações aplicadas.

Na raiz do repositório, execute `python3 scripts/prepare_native.py` para conferir e extrair as fontes em `native/source/`. A compilação utiliza essa árvore extraída. Os arquivos Cargo.lock, Cargo.toml, Makefile e LICENSE desta pasta preservam os metadados da base.

Veja [COMPILACAO.md](../docs/COMPILACAO.md) para configurar Zig, Rust e libopus. Use os atalhos e os caminhos KNULLI indicados no README principal; as instruções NextUI dentro do arquivo pertencem ao projeto original.
