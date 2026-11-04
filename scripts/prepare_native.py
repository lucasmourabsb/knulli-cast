#!/usr/bin/env python3
"""Unpack the complete, pinned native source tree supplied with this repo."""
import hashlib
import os
from pathlib import Path
import shutil
import tarfile
import tempfile

SHA256 = 'd0df4b0266e9aca701f3acfe49789bd03a3f3c4a9713e91e26c92b5b0e1c3d0f'


def prepare(destination=None):
    root = Path(__file__).resolve().parents[1]
    archive = root/'native/rgsp-cast-knulli-source.tar.gz'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise RuntimeError('O arquivo de fontes nativas não corresponde ao SHA-256 esperado.')
    destination = Path(destination) if destination else root/'native/source'
    marker = destination/'.knulli-source-sha256'
    if marker.exists() and marker.read_text().strip() == SHA256:
        return destination
    if destination.exists():
        raise RuntimeError('A pasta de fontes já existe. Preserve suas alterações antes de preparar outra cópia.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.knulli-source-',dir=destination.parent) as temporary:
        with tarfile.open(archive,'r:gz') as source:
            base = Path(temporary).resolve()
            for entry in source.getmembers():
                target = (base/entry.name).resolve()
                if not entry.isfile() or os.path.commonpath((str(base),str(target))) != str(base):
                    raise RuntimeError('O arquivo de fontes contém uma entrada inesperada.')
                target.parent.mkdir(parents=True,exist_ok=True)
                with source.extractfile(entry) as incoming, target.open('wb') as output:
                    shutil.copyfileobj(incoming,output)
                target.chmod(entry.mode & 0o777)
        (Path(temporary)/'.knulli-source-sha256').write_text(SHA256+'\n')
        shutil.move(temporary,destination)
    return destination


if __name__ == '__main__':
    print('Fontes preparadas:',prepare())
