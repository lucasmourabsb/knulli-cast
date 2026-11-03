#!/usr/bin/env python3
"""Download the exact upstream ARM64 executable used by this prototype."""
import hashlib
from pathlib import Path
import urllib.request

URL = 'https://github.com/AlexxIT/go2rtc/releases/download/v1.9.15/go2rtc_linux_arm64'
SHA256 = 'af416f22b21a24ab83b8d78642190b4932ae695b4e386853f11d1b0319781763'


def main():
    destination = Path(__file__).resolve().parents[1] / 'handheld' / 'go2rtc'
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read(32*1024*1024)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit('SHA-256 não confere. Nenhum executável foi instalado.')
    temporary = destination.with_suffix('.download')
    temporary.write_bytes(data)
    temporary.chmod(0o755)
    temporary.replace(destination)
    print('go2rtc ARM64 baixado e verificado:', destination)


if __name__ == '__main__':
    main()
