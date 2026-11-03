#!/usr/bin/env python3
"""Configure the same Zig/GNU cross-build used for the KNULLI adaptation."""
import os
from pathlib import Path
import shutil
import subprocess


def main():
    root = Path(__file__).resolve().parents[1]
    opus = Path(os.environ.get('OPUS_LIB_DIR', 'sysroot/lib')).resolve()
    if not (opus/'libopus.so').is_file():
        raise SystemExit('Configure OPUS_LIB_DIR com a libopus.so ARM64 do KNULLI.')
    for tool in ('cargo', 'cmake'):
        if not shutil.which(tool):
            raise SystemExit('Ferramenta necessária no PATH: '+tool)
    if not (os.environ.get('ZIG') or shutil.which('zig')):
        raise SystemExit('Configure ZIG ou adicione o Zig ao PATH.')
    tools = root/'tools'
    # A download through a web interface can lose executable mode bits.
    for wrapper in tools.glob('*.py'):
        wrapper.chmod(wrapper.stat().st_mode | 0o111)
    env = os.environ.copy()
    env.update({
        'OPUS_LIB_DIR': str(opus),
        'CC_aarch64_unknown_linux_gnu': str(tools/'zig_cc.py'),
        'CXX_aarch64_unknown_linux_gnu': str(tools/'zig_cxx.py'),
        'AR_aarch64_unknown_linux_gnu': str(tools/'zig_ar.py'),
        'CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER': str(tools/'zig_cc.py'),
        'PKG_CONFIG': str(tools/'opus_pkg_config.py'),
        'PKG_CONFIG_ALLOW_CROSS': '1',
    })
    subprocess.run(['cargo','build','--locked','--release','-p','rgsp-host',
                    '--target','aarch64-unknown-linux-gnu'],cwd=root/'native',env=env,check=True)
    binary = root/'native/target/aarch64-unknown-linux-gnu/release/rgsp-host'
    destination = root/'handheld/moonlight-host'
    shutil.copy2(binary,destination)
    destination.chmod(0o755)
    print('Servidor preparado:',destination)


if __name__ == '__main__':
    main()
