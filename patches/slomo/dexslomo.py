# Patch MiuiCamera classes.dex so slow motion records stretched (30 fps playback,
# 120 fps capture) like AOSP/Pixel slow motion, without audio. Usage: dexslomo.py in.dex out.dex
import struct, sys, zlib, hashlib
d = bytearray(open(sys.argv[1], "rb").read())
def u32(o): return struct.unpack_from("<I", d, o)[0]
def uleb(o):
    r = s = 0
    while True:
        b = d[o]; o += 1; r |= (b & 0x7f) << s; s += 7
        if b < 0x80: return r, o
sid_n, sid_o = u32(0x38), u32(0x3c); tid_n, tid_o = u32(0x40), u32(0x44)
fid_n, fid_o = u32(0x50), u32(0x54); mid_n, mid_o = u32(0x58), u32(0x5c)
cdef_n, cdef_o = u32(0x60), u32(0x64)
def string(i):
    o = u32(sid_o + 4 * i); _, o = uleb(o); e = d.index(0, o); return d[o:e].decode("utf-8", "replace")
def tname(i): return string(u32(tid_o + 4 * i))
def field(cls, name):
    for i in range(fid_n):
        c, t, n = struct.unpack_from("<HHI", d, fid_o + 8 * i)
        if tname(c) == cls and string(n) == name: return i
def method(cls, name):
    r = []
    for i in range(mid_n):
        c, p, n = struct.unpack_from("<HHI", d, mid_o + 8 * i)
        if tname(c) == cls and string(n) == name: r.append(i)
    return r
def code_of(cls, name):
    mids = set(method(cls, name))
    for i in range(cdef_n):
        o = cdef_o + 32 * i
        if tname(u32(o)) != cls: continue
        cd = u32(o + 24); o, _ = cd, 0
        sf, o = uleb(o); inf, o = uleb(o); dm, o = uleb(o); vm, o = uleb(o)
        for _ in range(sf + inf): _, o = uleb(o); _, o = uleb(o)
        m = 0
        for _ in range(dm + vm):
            dlt, o = uleb(o); m += dlt; _, o = uleb(o); co, o = uleb(o)
            if m in mids and co:
                ins = u32(co + 12); return co + 16, ins * 2
            if _ == 0: pass
        # note: m resets between direct and virtual lists
    raise SystemExit("method not found " + name)
def code_of2(cls, name):
    mids = set(method(cls, name))
    for i in range(cdef_n):
        o = cdef_o + 32 * i
        if tname(u32(o)) != cls: continue
        o = u32(o + 24)
        sf, o = uleb(o); inf, o = uleb(o); dm, o = uleb(o); vm, o = uleb(o)
        for _ in range(sf + inf): _, o = uleb(o); _, o = uleb(o)
        for cnt in (dm, vm):
            m = 0
            for _ in range(cnt):
                dlt, o = uleb(o); m += dlt; _, o = uleb(o); co, o = uleb(o)
                if m in mids and co: return co + 16, u32(co + 12) * 2
    raise SystemExit("method not found " + name)
RC = "Lcom/android/camera/module/video/RecorderController;"
URS = "Lcom/android/camera/module/video/UserRecordSetting;"
BLD = "Lcom/android/camera/module/video/MediaRecorderParameter$Builder;"
fr = field(URS, "mFrameRate"); svfr = method(BLD, "setVideoFrameRate"); flag = method("LOooO0O0/OooO0Oo/OooO00o/OooO00o;", "o000OO0O")
print("mFrameRate field", fr, "setVideoFrameRate", svfr, "o000OO0O", flag)
# 1) setupRecorderParameter: slow-motion branch = invoke o000OO0O; move-result v1; if-nez v1; iget-object v1,..; iget v1,v1,mFrameRate; invoke-virtual {v2,v1} setVideoFrameRate
start, size = code_of2(RC, "setupRecorderParameter")
code = bytes(d[start:start + size]); hits = []
for f in flag:
    pat = struct.pack("<BBH", 0x6e, 0x10, f)
    i = code.find(pat)
    while i >= 0:
        j = i + 6  # after invoke-virtual (3 units)
        if code[j:j+2] == b"\x0a\x01" and code[j+2] == 0x39 and code[j+3] == 0x01:
            k = j + 2 + 4 + 4  # skip move-result, if-nez(2u), iget-object(2u)
            if code[k] == 0x52 and code[k+1] == 0x11 and struct.unpack_from("<H", code, k+2)[0] == fr and \
               code[k+4] == 0x6e and code[k+5] == 0x20 and struct.unpack_from("<H", code, k+6)[0] in svfr:
                hits.append(k)
        i = code.find(pat, i + 1)
assert len(hits) == 1, hits
k = start + hits[0]
d[k:k+4] = bytes([0x13, 0x01]) + struct.pack("<h", 30)   # const/16 v1, 30
print("patched setVideoFrameRate(120) -> 30 at dex", hex(k))
# 2) recordAudio: invoke o000OO0O; move-result v1; const/4 v2,1; xor-int/2addr v1,v2  -> const/4 v1,0
start, size = code_of2(URS, "recordAudio")
code = bytes(d[start:start + size]); hits = []
for f in flag:
    pat = struct.pack("<BBH", 0x6e, 0x10, f) + b"\x01\x00\x0a\x01\x12\x12\xb7\x21"
    i = code.find(pat)
    if i >= 0: hits.append(i + len(pat) - 2)
assert len(hits) == 1, hits
k = start + hits[0]
d[k:k+2] = b"\x12\x01"   # const/4 v1, 0
print("patched recordAudio xor -> const/4 v1,0 at dex", hex(k))
d[12:32] = hashlib.sha1(d[32:]).digest()
d[8:12] = struct.pack("<I", zlib.adler32(bytes(d[12:])) & 0xffffffff)
open(sys.argv[2], "wb").write(d)
