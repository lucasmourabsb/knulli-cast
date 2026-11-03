#!/usr/bin/env python3
import os
import shutil
import sys
zig = os.environ.get('ZIG') or shutil.which('zig')
if not zig:
    raise SystemExit('Configure ZIG ou adicione o Zig ao PATH.')
os.execv(zig,[zig,'ar',*sys.argv[1:]])
