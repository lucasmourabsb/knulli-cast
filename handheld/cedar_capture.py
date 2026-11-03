#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
# Python adaptation of the CedarC capture ABI and lifecycle in
# https://github.com/codebutler/rgsp-cast (rgsp-cedar, GPL-3.0).
"""Direct framebuffer-to-H.264 capture using the H700 video engine."""
import ctypes as C
import fcntl
import os
import signal
import struct
import subprocess
import sys
import time
from pathlib import Path

P, I, U, B = C.c_void_p, C.c_int, C.c_uint, C.c_ubyte
FPS = 60
running = True


class Base(C.Structure):
    _fields_ = [('nalu', B), ('w', U), ('h', U), ('dw', U), ('dh', U),
                ('stride', U), ('fmt', I), ('memops', P), ('veops', P),
                ('selfops', P), ('flags', B * 4), ('tail', B * (128 + 4096))]


class Input(C.Structure):
    _fields_ = [('vir_y', P), ('vir_c', P), ('phy_y', P), ('phy_c', P),
                ('phy_uv', P), ('cpu_y', P), ('cpu_uv', P), ('id', I), ('pad', I),
                ('pts', C.c_int64), ('duration', C.c_int64), ('first', I),
                ('last', I), ('crop', I), ('fd', U), ('tail', B * (256 + 4096))]


class Output(C.Structure):
    _fields_ = [('id', I), ('pts', C.c_int64), ('flags', U),
                ('size0', U), ('size1', U), ('data0', P), ('data1', P),
                ('tail', B * (256 + 4096))]


class Allocate(C.Structure):
    _fields_ = [('count', U), ('size_y', U), ('size_c', U), ('tail', B * (64 + 4096))]


class Header(C.Structure):
    _fields_ = [('data', P), ('length', U), ('tail', B * (496 + 4096))]


def geometry(fd):
    data = bytearray(160)
    fcntl.ioctl(fd, 0x4600, data, True)
    return struct.unpack_from('7I', data)


def annexb(raw):
    if raw.startswith((b'\x00\x00\x00\x01', b'\x00\x00\x01')):
        return raw
    result = bytearray()
    pos = 0
    while pos + 4 <= len(raw):
        size = int.from_bytes(raw[pos:pos+4], 'big')
        pos += 4
        if not size or pos + size > len(raw):
            return raw
        result += b'\x00\x00\x00\x01' + raw[pos:pos+size]
        pos += size
    return bytes(result) if pos == len(raw) else raw


def parameter_sets(raw):
    if not raw or raw[0] != 1:
        return annexb(raw)
    result = bytearray()
    pos = 6
    for _ in range(raw[5] & 31):
        size = int.from_bytes(raw[pos:pos+2], 'big'); pos += 2
        result += b'\x00\x00\x00\x01' + raw[pos:pos+size]; pos += size
    count = raw[pos]; pos += 1
    for _ in range(count):
        size = int.from_bytes(raw[pos:pos+2], 'big'); pos += 2
        result += b'\x00\x00\x00\x01' + raw[pos:pos+size]; pos += size
    return bytes(result)


def stop(*_):
    global running
    running = False


def fast_wifi():
    for interface in Path('/sys/class/net').iterdir():
        if not ((interface/'wireless').exists() or (interface/'phy80211').exists()):
            continue
        try:
            state = subprocess.run(['iw', 'dev', interface.name, 'get', 'power_save'],
                                   capture_output=True, text=True, timeout=2)
            if 'Power save: on' in state.stdout:
                changed = subprocess.run(['iw', 'dev', interface.name, 'set', 'power_save', 'off'],
                                         capture_output=True, timeout=2)
                if changed.returncode == 0:
                    return interface.name
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


class Encoder:
    def __init__(self, width, height):
        self.enc = None
        self.mem_open = self.initialized = self.allocated = False
        self.libs = []
        root = Path(__file__).resolve().parent / 'lib'
        for name in ['libVE.so', 'libMemAdapter.so', 'libvencoder.so']:
            self.libs.append(C.CDLL(str(root/name), mode=os.RTLD_LAZY | os.RTLD_GLOBAL))
        ve, mem, venc = self.libs

        def bind(lib, name, result, *args):
            fn = getattr(lib, name)
            fn.restype = result
            fn.argtypes = args
            return fn

        self.create = bind(venc, 'VideoEncCreate', P, I)
        self.init = bind(venc, 'VideoEncInit', I, P, C.POINTER(Base))
        self.uninit = bind(venc, 'VideoEncUnInit', None, P)
        self.destroy = bind(venc, 'VideoEncDestroy', None, P)
        self.allocate = bind(venc, 'AllocInputBuffer', I, P, C.POINTER(Allocate))
        self.release = bind(venc, 'ReleaseAllocInputBuffer', I, P)
        self.acquire = bind(venc, 'GetOneAllocInputBuffer', I, P, C.POINTER(Input))
        self.flush = bind(venc, 'FlushCacheAllocInputBuffer', I, P, C.POINTER(Input))
        self.submit = bind(venc, 'AddOneInputBuffer', I, P, C.POINTER(Input))
        self.encode = bind(venc, 'VideoEncodeOneFrame', I, P)
        self.valid = bind(venc, 'ValidBitstreamFrameNum', I, P)
        self.output = bind(venc, 'GetOneBitstreamFrame', I, P, C.POINTER(Output))
        self.free_output = bind(venc, 'FreeOneBitStreamFrame', I, P, C.POINTER(Output))
        self.used = bind(venc, 'AlreadyUsedInputBuffer', I, P, C.POINTER(Input))
        self.recycle = bind(venc, 'ReturnOneAllocInputBuffer', I, P, C.POINTER(Input))
        self.get = bind(venc, 'VideoEncGetParameter', I, P, I, P)
        self.set = bind(venc, 'VideoEncSetParameter', I, P, I, P)
        veops = bind(ve, 'GetVeOpsS', P, I)(0)
        memops = bind(mem, 'MemAdapterGetOpsS', P)()
        if not veops or not memops:
            raise RuntimeError('O chip não forneceu os recursos de vídeo.')
        self.ops = C.cast(memops, C.POINTER(P * 20)).contents
        self.mem_close = C.CFUNCTYPE(None)(self.ops[2])
        self.to_virtual = C.CFUNCTYPE(P, P)(self.ops[9])
        if C.CFUNCTYPE(I)(self.ops[0])() < 0:
            raise RuntimeError('Não foi possível abrir a memória de vídeo.')
        self.mem_open = True
        self.enc = self.create(0)
        if not self.enc:
            raise RuntimeError('O codificador do chip não está disponível.')
        bitrate = I(2500000)
        if self.set(self.enc, 0, C.byref(bitrate)) != 0:
            raise RuntimeError('O chip rejeitou a configuração de vídeo.')
        framerate = I(FPS)
        self.set(self.enc, 1, C.byref(framerate))
        cfg = Base()
        cfg.nalu = 1
        cfg.w = cfg.dw = cfg.stride = width
        cfg.h = cfg.dh = height
        cfg.fmt = 12  # ARGB word order = B,G,R,A framebuffer bytes.
        cfg.memops = memops
        cfg.veops = veops
        if self.init(self.enc, C.byref(cfg)) != 0:
            raise RuntimeError('Não foi possível iniciar o codificador do chip.')
        self.initialized = True
        buf = Allocate()
        buf.count = 1
        buf.size_y = width * height * 4
        if self.allocate(self.enc, C.byref(buf)) != 0:
            raise RuntimeError('O chip não conseguiu reservar um quadro.')
        self.allocated = True
        interval = I(FPS)
        self.set(self.enc, 2, C.byref(interval))
        self.headers = b''
        self.frames = 0
        self.width, self.height = width, height

    def frame(self, raw):
        source = Input()
        if self.acquire(self.enc, C.byref(source)) != 0 or not source.cpu_y:
            raise RuntimeError('Falha ao obter um quadro do codificador.')
        C.memmove(source.cpu_y, raw, len(raw))
        source.pts = self.frames * (1000000 // FPS)
        source.first = int(self.frames == 0)
        self.flush(self.enc, C.byref(source))
        if self.submit(self.enc, C.byref(source)) != 0 or self.encode(self.enc) != 0:
            raise RuntimeError('Falha ao codificar o quadro.')
        if not self.frames:
            header = Header()
            if self.get(self.enc, 0x101, C.byref(header)) == 0 and header.data and 0 < header.length <= 512:
                addr = self.to_virtual(header.data) or header.data
                self.headers = parameter_sets(C.string_at(addr, header.length))
        result = bytearray()
        key = False
        while self.valid(self.enc) > 0:
            out = Output()
            if self.output(self.enc, C.byref(out)) != 0:
                raise RuntimeError('Falha ao receber o quadro codificado.')
            try:
                total = out.size0 + out.size1
                if not 0 < total <= 4*1024*1024 or (out.size0 and not out.data0) or (out.size1 and not out.data1):
                    raise RuntimeError('O codificador retornou um quadro inválido.')
                frame = C.string_at(out.data0, out.size0) if out.size0 else b''
                if out.size1:
                    frame += C.string_at(out.data1, out.size1)
                result += annexb(frame)
                key |= bool(out.flags & 1)
            finally:
                self.free_output(self.enc, C.byref(out))
        used = Input()
        if self.used(self.enc, C.byref(used)) == 0:
            self.recycle(self.enc, C.byref(used))
        if not self.frames or key:
            result = self.headers + result
        self.frames += 1
        return result

    def close(self):
        if self.enc:
            if self.allocated:
                self.release(self.enc)
            if self.initialized:
                self.uninit(self.enc)
            self.destroy(self.enc)
            self.enc = None
        if self.mem_open:
            self.mem_close()
            self.mem_open = False


def main():
    library_path = str(Path(__file__).resolve().parent / 'lib')
    if os.environ.get('LD_LIBRARY_PATH') != library_path:
        env = os.environ.copy()
        env['LD_LIBRARY_PATH'] = library_path
        os.execve(sys.executable, [sys.executable, __file__, *sys.argv[1:]], env)
    # Keep vendor diagnostic prints out of the compressed stream.
    output_fd = os.dup(1)
    os.dup2(2, 1)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    fb = os.open('/dev/fb0', os.O_RDONLY)
    width, height, _, _, _, _, bpp = geometry(fb)
    stride = int(Path('/sys/class/graphics/fb0/stride').read_text())
    if bpp != 32 or stride != width*4 or width % 16 or height % 16:
        raise RuntimeError('A tela atual não é compatível com a captura direta.')
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    encoder = None
    wifi = fast_wifi()
    started = time.monotonic()
    deadline = started
    try:
        encoder = Encoder(width, height)
        while running and (not duration or time.monotonic() - started < duration):
            current = geometry(fb)
            if current[:2] != (width, height) or current[6] != bpp:
                raise RuntimeError('A resolução da tela mudou. Reconecte.')
            raw = os.pread(fb, stride*height, current[5]*stride+current[4]*4)
            if len(raw) != stride*height:
                raise RuntimeError('A captura retornou um quadro incompleto.')
            view = memoryview(encoder.frame(raw))
            while view and running:
                view = view[os.write(output_fd, view):]
            deadline += 1/FPS
            delay = deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            elif delay < -1/FPS:
                deadline = time.monotonic()
    except BrokenPipeError:
        pass
    finally:
        if encoder:
            encoder.close()
            print(f'Hardware: {encoder.frames} quadros em {time.monotonic()-started:.2f}s', file=sys.stderr)
        if wifi:
            subprocess.run(['iw', 'dev', wifi, 'set', 'power_save', 'on'],
                           capture_output=True, timeout=2)
        os.close(fb)
        os.close(output_fd)


if __name__ == '__main__':
    main()
