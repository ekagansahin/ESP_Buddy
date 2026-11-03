# ESP_Buddy protocol and file formats (v0.2)

The ESP32 plays two kinds of screen files:

- **`.olb`** holds pre-rendered 1-bit frames. Weather, markets, faces and the rest are all drawn in Python by GitHub Actions, so the web preview matches the device pixel for pixel.
- **`.liv`** is a screen the device draws itself. For now the only one is the **live clock**, which ticks every second because it is drawn on the device.

All numbers are little-endian.

## 1. `.olb`

| Byte | Field | Notes |
|---|---|---|
| 0–3 | magic | ASCII `OLB1` |
| 4 | `w` | width, 1–128 |
| 5 | `h` | height, 1–64 |
| 6–7 | `frames` | frame count, ≥ 1 (1 = static screen) |
| 8–9 | `duration` | display time in seconds; 0 = device default |
| 10 | `flags` | bit0 = frames are PackBits-compressed |
| 11–15 | — | 0 |

The frames follow the header. Each frame is one of:

- **uncompressed:** `u16 delay_ms`, then `ceil(w/8)*h` bytes of bitmap.
- **PackBits:** `u16 delay_ms`, `u16 packed_len`, then the packed data. It unpacks to `ceil(w/8)*h` bytes.

Bitmap layout is row by row, each row padded to a whole byte, **most significant bit = leftmost pixel**, 1 = lit. This is the same layout Adafruit GFX `drawBitmap` uses. Images smaller than the screen are centred.

PackBits header byte `n`:

| `n` | Meaning |
|---|---|
| `0–127` | copy the next `n+1` bytes |
| `129–255` | repeat the next byte `257−n` times |
| `128` | no-op |

## 2. `.liv`

| Byte | Field | Notes |
|---|---|---|
| 0–3 | magic | ASCII `LIV1` |
| 4 | `type` | 1 = clock |
| 5 | `lang` | 0 = English, 1 = Turkish (month and day names) |
| 6–7 | — | 0 |
| 8–9 | `duration` | display time in seconds |
| 10–11 | `text_len` | 0–64 |
| 12–15 | — | 0 |
| 16… | text | UTF-8 info line under the clock, e.g. `Ankara 13°  $49.91` |

The clock screen is laid out top to bottom:

- the date line: `Mon 2 November` in English, `2 Kasım Pazartesi` in Turkish
- a large `HH:MM` with a blinking colon
- a seconds bar
- the info line

This layout is identical to `clock_preview()` in `generator/screens.py`. The clock screen is skipped until the phone has sent `TIME`.

Besides ASCII, the device font has `Ç ç Ğ ğ İ ı Ö ö Ş ş Ü ü ° ·`. Any other character shows as `?`.

## 3. Playback

- Files are stored in the LittleFS folder `/s/` and played **in file-name order** (`01-clock.liv`, `02-weather-now.olb`, …).
- Names:
  - at most 24 characters,
  - only `A-Z a-z 0-9 . - _`,
  - must not start with a dot.
- A file may be at most 48000 bytes.
- A static screen stays for `duration` seconds. An animation loops until `duration` has passed, then finishes its current loop before moving on, so it always plays at least one full loop.
- With nothing to play, the device shows an idle screen.
- In receive mode, after 30 s without any activity, the device goes back to playing.
- Between 00:00 and 07:00 the display dims (once the time is known).

## 4. BLE service

Device name: `ESP_Buddy`

| | UUID | Properties |
|---|---|---|
| Service | `68961d5e-4b75-4893-bb3e-14ce93b54693` | |
| `command` | `0c3fb439-03a5-4085-ad4e-c2975815cf1a` | write (with response), ASCII text |
| `data` | `c34519c8-f6e2-4dba-9be7-f5591b429020` | write / write without response, raw bytes |
| `status` | `ae53dc3e-1ba9-4f77-b87c-428aa72328e8` | notify, ASCII replies |

Keep `data` chunks at **≤ 180 bytes**, because the iPhone MTU is 185. After every command, wait for its `OK …` or `ERR …` reply.

**Flow control:** iOS queues writes without response, and a long queue delays the commands behind it. So the page keeps at most 2 KB in flight beyond the last `PROGRESS`, and sends `DONE` only after `PROGRESS` reports the whole file. If `DONE` still arrives before the last bytes, the device waits up to 3 s for them.

## 5. Commands

| Command | Reply | Effect |
|---|---|---|
| `TIME <unix_s> [offset_min]` | `OK TIME 14:05:10` | Sets the clock. The offset defaults to 180 (UTC+3). Time keeps running until power is lost. |
| `CLEAR` | `OK CLEAR <n>` | Deletes every screen and enters receive mode. |
| `FILE <name> <bytes> <crc32hex>` | `READY <name>` | Starts receiving a file. CRC-32 is the same as zlib's. |
| *(data writes)* | `PROGRESS <bytes>` every 1 KB and once when the file is complete | The page uses these as flow control |
| `DONE` | `OK DONE <name>` or `ERR DONE length\|crc\|format\|space` | Checks length, CRC and format, then saves to flash. |
| `ABORT` | `OK ABORT` | Drops a half-received file. |
| `SHOW` | `OK SHOW <n>` | Leaves receive mode and starts from the first screen. |
| `DELETE <name>` | `OK DELETE <name>` | Deletes one file. |
| `LIST` | `L <name> <bytes>` … then `OK LIST <n>` | Lists the files. |
| `NEXT` / `PREV` | `OK NEXT <index>` | Remote control. |
| `PAUSE` / `RESUME` | `OK PAUSE` / `OK RESUME` | Stops or resumes the automatic rotation. |
| `BRIGHTNESS <0-255>` | `OK BRIGHTNESS <v>` | Daytime brightness. |
| `DURATION <s>` | `OK DURATION <s>` | Default time for screens whose header says 0. |
| `INFO` | `INFO v0.2 screens=… at=… time=… fs=… heap=… block=…` | Status. `block` is the largest free memory block. |
| `DEMO` | `OK DEMO 4` | Offline test: creates 4 demo screens, replacing the current ones. |

You can also type the commands in the USB Serial Monitor (115200 baud, line ending "Newline").

The web page's **Connect & send** button sends `TIME`, then `CLEAR`, then `FILE` / data / `DONE` for each file, and finally `SHOW`. If `DONE` fails, the file is resent up to 3 times; from the second attempt the data writes are acknowledged. Whatever happens, the page sends `SHOW` at the end so the device never stays stuck in receive mode.
