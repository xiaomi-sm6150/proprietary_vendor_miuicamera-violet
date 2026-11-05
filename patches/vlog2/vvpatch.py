# Usage: vvpatch.py <vlog2 lib/arm64-v8a/libvvmediaeditor.so (md5 4347fa91c87a841b3ff47fc2c29ba663)> <out> <clang bin dir>
# Patch libvvmediaeditor.so (MIUI Camera vlog2 split) for Codec2 encoders:
# copy MediaCodec output from base+BufferInfo.offset and strip the SPS/PPS that
# c2.qti.avc.encoder prepends to IDR frames (the lib files any buffer starting
# with an SPS as codec config, so the first IDR never reached the muxer).
import os, struct, subprocess, sys, tempfile
src, dst, llvm = sys.argv[1:4]
d = bytearray(open(src, "rb").read())
CAVE = 0x98dc00          # zero padding after the R E segment (filesz 0x98dbfc)
SITE = 0x4017fc          # mov x1, x28   (before mov x2, x25 ; add x27.. ; bl memcpy)
RET  = 0x401804
LOGP = 0x0fe530          # __android_log_print@plt
assert d[SITE:SITE+4] == bytes.fromhex("e1031caa"), d[SITE:SITE+4].hex()   # mov x1, x28
assert d[SITE+4:SITE+8] == bytes.fromhex("e20319aa"), d[SITE+4:SITE+8].hex() # mov x2, x25
assert not any(d[CAVE:CAVE+0x200])
def rel(t, at): return t - (CAVE + at)
asm_lines = [
    "ldrsw x1, [sp, #0x138]",
    "add x1, x28, x1",          # src = base + offset
    "mov x2, x25",
    # Codec2 QTI prepends SPS/PPS to IDR frames; the lib then files the whole
    # IDR as codec config (data[4] == SPS) and never muxes it. Drop leading
    # SPS/PPS NALs from key frames that are not codec-config buffers.
    "ldr w10, [sp, #0x148]",
    "tbnz w10, #1, 9f",
    "tbz w10, #0, 9f",
    "ldrb w11, [x1, #4]",
    "and w11, w11, #0x1f",
    "cmp w11, #7",
    "b.ne 9f",
    "mov x10, #0",
    "movz w15, #0x100, lsl #16",
    "1:",
    "sub x14, x2, #5",
    "cmp x10, x14",
    "b.ge 9f",
    "ldr w12, [x1, x10]",
    "cmp w12, w15",
    "b.ne 2f",
    "add x11, x1, x10",
    "ldrb w13, [x11, #4]",
    "and w13, w13, #0x1f",
    "cmp w13, #7",
    "b.eq 2f",
    "cmp w13, #8",
    "b.eq 2f",
    "add x1, x1, x10",
    "sub x2, x2, x10",
    "mov x25, x2",
    "b 9f",
    "2:",
    "add x10, x10, #1",
    "b 1b",
    "9:",
    "mov x0, x26",
    "JMP_RET",
]
# assemble once to know offsets of CALL/JMP, then fix them as raw encodings
def enc_b(frm, to, link):
    off = (to - frm) // 4
    assert -(1 << 25) <= off < (1 << 25)
    return struct.pack("<I", (0x94000000 if link else 0x14000000) | (off & 0x3ffffff))
body = []
for l in asm_lines:
    body.append("nop" if l in ("CALL_LOG", "JMP_RET") else l)
s = ".text\n.globl _start\n_start:\n" + "\n".join(body) + '\n.balign 4\n'
with tempfile.TemporaryDirectory() as t:
    open(f"{t}/c.s", "w").write(s)
    subprocess.check_call([f"{llvm}/clang", "--target=aarch64-linux-android", "-c", f"{t}/c.s", "-o", f"{t}/c.o"])
    subprocess.check_call([f"{llvm}/llvm-objcopy", "-O", "binary", "--only-section=.text", f"{t}/c.o", f"{t}/c.bin"])
    code = bytearray(open(f"{t}/c.bin", "rb").read())
def boff(m):
    return 4 * sum(1 for l in asm_lines[:asm_lines.index(m)] if not l.endswith(":"))
ji = boff("JMP_RET")
code[ji:ji+4] = enc_b(CAVE + ji, RET, False)
d[CAVE:CAVE+len(code)] = code
d[SITE:SITE+4] = enc_b(SITE, CAVE, False)
# grow PT_LOAD[0] (R E) to cover the cave
phoff = struct.unpack_from("<Q", d, 0x20)[0]; phentsize, phnum = struct.unpack_from("<HH", d, 0x36)
for i in range(phnum):
    o = phoff + i * phentsize
    ptype, flags, off, va, pa, fsz, msz = struct.unpack_from("<IIQQQQQ", d, o)
    if ptype == 1 and off == 0:
        new = CAVE + len(code)
        assert new <= 0x98e7b8 and new > fsz
        struct.pack_into("<QQ", d, o + 0x20, new, new)
        print(f"PT_LOAD0 filesz/memsz {fsz:#x} -> {new:#x}")
        break
open(dst, "wb").write(d)
print("cave bytes", len(code))
