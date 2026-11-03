#!/usr/bin/env python3
import os
import shutil
import sys


def main(mode='cc'):
    zig = os.environ.get('ZIG') or shutil.which('zig')
    if not zig:
        raise SystemExit('Configure ZIG ou adicione o Zig ao PATH.')
    args = []
    raw = iter(sys.argv[1:])
    for argument in raw:
        if argument in ('-target','--target'):
            next(raw,None)
        elif argument == '-Wl,--fix-cortex-a53-843419':
            continue
        elif not argument.startswith('--target='):
            args.append(argument)
    os.execv(zig,[zig,mode,'-target','aarch64-linux-gnu.2.31',*args])


if __name__ == '__main__':
    main()
