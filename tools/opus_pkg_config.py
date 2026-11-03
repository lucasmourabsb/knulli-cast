#!/usr/bin/env python3
import os
from pathlib import Path
import sys
args = sys.argv[1:]
if not any(value == 'opus' or value.startswith('opus ') for value in args):
    raise SystemExit(1)
root = Path(os.environ['OPUS_LIB_DIR']).resolve()
if '--modversion' in args:
    print('1.4')
elif '--variable=libdir' in args:
    print(root)
elif '--variable=prefix' in args:
    print(root.parent)
elif '--libs' in args or '--cflags' in args:
    print('-L'+str(root)+' -lopus')
