"""ESP_Buddy screen files: .olb (pre-rendered 1-bit frames) and .liv (a screen the device draws live).

Format details: PROTOCOL.md
"""
import struct

from PIL import Image

W, H = 128, 64
FLAG_PACKBITS = 1
LIVE_CLOCK = 1
LANG_CODES = {"en": 0, "tr": 1}


def packbits(data: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        j = i
        while j + 1 < n and data[j + 1] == data[i] and j - i < 127:
            j += 1
        run = j - i + 1
        if run >= 3:
            out += bytes([257 - run, data[i]])
            i = j + 1
            continue
        start = i
        i += 1
        while i < n and i - start < 128:
            if i + 2 < n and data[i] == data[i + 1] == data[i + 2]:
                break
            i += 1
        out.append(i - start - 1)
        out += data[start:i]
    return bytes(out)


def unpackbits(data: bytes, length: int) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data) and len(out) < length:
        h = data[i]
        i += 1
        if h < 128:
            out += data[i:i + h + 1]
            i += h + 1
        elif h > 128:
            out += bytes([data[i]]) * (257 - h)
            i += 1
    return bytes(out[:length])


def frame_bytes(img: Image.Image) -> bytes:
    if img.mode != "1":
        img = img.convert("1")
    return img.tobytes()  # row by row, MSB = leftmost pixel, 1 = lit


def olb(frames, duration=0) -> bytes:
    """frames: [(PIL '1' image, delay_ms), ...] — all the same size."""
    w, h = frames[0][0].size
    assert 1 <= w <= W and 1 <= h <= H
    raw = [frame_bytes(f) for f, _ in frames]
    packed = [packbits(b) for b in raw]
    compress = sum(len(p) + 4 for p in packed) < sum(len(b) + 2 for b in raw)
    head = b"OLB1" + struct.pack("<BBHHB5x", w, h, len(frames), int(duration), FLAG_PACKBITS if compress else 0)
    body = bytearray()
    for (_, ms), b, p in zip(frames, raw, packed):
        ms = max(0, min(65535, int(ms)))
        if compress:
            body += struct.pack("<HH", ms, len(p)) + p
        else:
            body += struct.pack("<H", ms) + b
    return head + bytes(body)


def live(kind, duration=0, text="", lang="en") -> bytes:
    t = text.encode("utf-8")[:64]
    return b"LIV1" + struct.pack("<BB2xHH4x", kind, LANG_CODES[lang], int(duration), len(t)) + t


def olb_decode(data: bytes):
    """For tests and previews: [(PIL image, ms)], duration"""
    assert data[:4] == b"OLB1"
    w, h, n, duration, flags = struct.unpack("<BBHHB", data[4:11])
    fb = (w + 7) // 8 * h
    i, frames = 16, []
    for _ in range(n):
        ms = struct.unpack("<H", data[i:i + 2])[0]
        i += 2
        if flags & FLAG_PACKBITS:
            ln = struct.unpack("<H", data[i:i + 2])[0]
            i += 2
            b = unpackbits(data[i:i + ln], fb)
            i += ln
        else:
            b = data[i:i + fb]
            i += fb
        frames.append((Image.frombytes("1", (w, h), b), ms))
    assert i == len(data), "size mismatch"
    return frames, duration
