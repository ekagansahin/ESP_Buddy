// ESP_Buddy — ESP32 + SSD1306 128x64 + BLE
//
// The phone (GitHub Pages site, Web Bluetooth) sends screen files over BLE. The ESP32 stores
// them in LittleFS and plays them in file-name order, forever.
//   .olb : pre-rendered 1-bit frames (weather, markets, faces...), optionally PackBits-compressed
//   .liv : a screen the device draws live (for now: the clock), in English or Turkish
// The time comes from the phone (TIME command) and keeps running until power is lost.
// No buttons, the screen never turns off (it dims at night). Protocol: ../../PROTOCOL.md
//
// Library: Adafruit SSD1306 (+ Adafruit GFX, BusIO). Board: ESP32 Dev Module.

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <FS.h>
#include <LittleFS.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <esp_heap_caps.h>
#include <sys/time.h>
#include <time.h>
#include <vector>
#include <algorithm>
#include "config.h"
#include "font_text.h"
#include "font_clock.h"

// ---------------------------------------------------------------------------
// File formats — see PROTOCOL.md
// ---------------------------------------------------------------------------
static const size_t HEADER = 16;
static const size_t FRAME_MAX = (SCREEN_W / 8) * SCREEN_H;   // 1024 bytes
static const size_t PACKED_MAX = FRAME_MAX + FRAME_MAX / 128 + 8;
static const uint8_t FLAG_PACKBITS = 1;
static const uint8_t LIVE_CLOCK = 1;
static const uint8_t LANG_EN = 0, LANG_TR = 1;

enum Kind : uint8_t { KIND_OLB = 1, KIND_LIVE = 2 };

struct Header {
  Kind     kind;
  uint8_t  w, h;      // OLB
  uint16_t frames;    // OLB
  uint16_t duration;
  uint8_t  flags;     // OLB
  uint8_t  liveType;  // LIVE
  uint8_t  lang;      // LIVE
  uint16_t textLen;   // LIVE
};

static inline uint16_t le16(const uint8_t* p) { return (uint16_t)p[0] | ((uint16_t)p[1] << 8); }
static size_t frameBytes(uint8_t w, uint8_t h) { return (size_t)((w + 7) / 8) * h; }

// Parses the 16-byte header only
static bool parseHeader(const uint8_t* b, Header& o) {
  o.duration = le16(b + 8);
  if (memcmp(b, "OLB1", 4) == 0) {
    o.kind = KIND_OLB;
    o.w = b[4]; o.h = b[5]; o.frames = le16(b + 6); o.flags = b[10];
    return o.w >= 1 && o.w <= SCREEN_W && o.h >= 1 && o.h <= SCREEN_H && o.frames >= 1;
  }
  if (memcmp(b, "LIV1", 4) == 0) {
    o.kind = KIND_LIVE;
    o.liveType = b[4]; o.lang = b[5]; o.textLen = le16(b + 10);
    return o.liveType == LIVE_CLOCK && o.textLen <= 64;
  }
  return false;
}

// Validates a complete file held in RAM (at the end of a transfer)
static bool validateFile(const uint8_t* p, size_t n) {
  if (n < HEADER) return false;
  Header b;
  if (!parseHeader(p, b)) return false;
  if (b.kind == KIND_LIVE) return n == HEADER + b.textLen;
  size_t fb = frameBytes(b.w, b.h), i = HEADER;
  for (uint16_t k = 0; k < b.frames; k++) {
    if (b.flags & FLAG_PACKBITS) {
      if (i + 4 > n) return false;
      size_t len = le16(p + i + 2);
      if (len > PACKED_MAX) return false;
      i += 4 + len;
    } else {
      i += 2 + fb;
    }
    if (i > n) return false;
  }
  return i == n;
}

// PackBits decoder; the output must be exactly 'outLen' bytes
static bool unpackbits(const uint8_t* src, size_t n, uint8_t* dst, size_t outLen) {
  size_t i = 0, o = 0;
  while (i < n && o < outLen) {
    uint8_t h = src[i++];
    if (h < 128) {
      size_t c = h + 1;
      if (i + c > n || o + c > outLen) return false;
      memcpy(dst + o, src + i, c);
      i += c; o += c;
    } else if (h > 128) {
      size_t c = 257 - h;
      if (i >= n || o + c > outLen) return false;
      memset(dst + o, src[i++], c);
      o += c;
    }
  }
  return o == outLen;
}

// Standard CRC-32 (same as zlib / the web page)
static uint32_t crc32(const uint8_t* p, size_t n) {
  uint32_t c = 0xFFFFFFFFu;
  while (n--) {
    c ^= *p++;
    for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1u)));
  }
  return c ^ 0xFFFFFFFFu;
}

static bool validName(const char* name) {
  size_t n = strlen(name);
  if (n < 1 || n > 24 || name[0] == '.') return false;
  for (size_t i = 0; i < n; i++) {
    char c = name[i];
    if (!(isalnum((unsigned char)c) || c == '.' || c == '-' || c == '_')) return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Text: UTF-8 -> FontText codes (ASCII + extras starting at 0x7F)
// Same order as DEVICE_EXTRA in tools/prepare_fonts.py: ÇçĞğİıÖöŞşÜü°·
// ---------------------------------------------------------------------------
static const uint16_t TEXT_EXTRA[] = {0xC7, 0xE7, 0x11E, 0x11F, 0x130, 0x131, 0xD6, 0xF6, 0x15E, 0x15F, 0xDC, 0xFC, 0xB0, 0xB7};

void toFontCodes(const char* in, char* out, size_t outLen) {
  size_t o = 0;
  const uint8_t* s = (const uint8_t*)in;
  while (*s && o + 1 < outLen) {
    uint32_t cp;
    if (*s < 0x80) cp = *s++;
    else if ((*s & 0xE0) == 0xC0 && s[1]) { cp = ((s[0] & 0x1F) << 6) | (s[1] & 0x3F); s += 2; }
    else if ((*s & 0xF0) == 0xE0 && s[1] && s[2]) { cp = ((s[0] & 0x0F) << 12) | ((s[1] & 0x3F) << 6) | (s[2] & 0x3F); s += 3; }
    else { s++; cp = '?'; }
    char c = '?';
    if (cp >= 0x20 && cp < 0x7F) c = (char)cp;
    else for (size_t k = 0; k < sizeof(TEXT_EXTRA) / sizeof(TEXT_EXTRA[0]); k++) if (TEXT_EXTRA[k] == cp) { c = (char)(0x7F + k); break; }
    out[o++] = c;
  }
  out[o] = 0;
}

int textWidth(const GFXfont* f, const char* s) {
  int w = 0;
  for (; *s; s++) {
    uint8_t c = (uint8_t)*s;
    if (c < f->first || c > f->last) continue;
    w += f->glyph[c - f->first].xAdvance;
  }
  return w;
}

// ---------------------------------------------------------------------------
// Global state
// ---------------------------------------------------------------------------
Adafruit_SSD1306 display(SCREEN_W, SCREEN_H, &Wire, -1);

BLEServer*         server     = nullptr;
BLECharacteristic* statusChr  = nullptr;
volatile bool      connected  = false;
volatile bool      advertisePending = false;
uint32_t           advertiseAt = 0;

static const size_t MSG_MAX = 100;
struct Msg { char s[MSG_MAX]; };
QueueHandle_t commandQueue;   // BLE/Serial -> loop
QueueHandle_t replyQueue;     // anyone -> loop (notify + Serial)

// Receiving (written by the BLE task, read by loop)
volatile bool     receiving  = false;   // while true, playback is paused
uint8_t* volatile rxBuf      = nullptr;
volatile size_t   rxLen      = 0;
volatile size_t   rxExpected = 0;
volatile bool     rxOverflow = false;
volatile bool     rxClosed   = true;
volatile uint32_t lastRxActivity = 0;
portMUX_TYPE      rxMux      = portMUX_INITIALIZER_UNLOCKED;   // guards rxBuf/rxLen between the BLE task and loop()
bool              donePending = false;  // DONE arrived while bytes were still in flight
uint32_t          doneDeadline = 0;
uint32_t          rxCrc      = 0;
char              rxName[32] = "";
int               receivedCount = 0;

// Clock
bool     timeKnown = false;
int32_t  utcOffset = DEFAULT_OFFSET_MIN * 60;

// Brightness
uint8_t dayContrast = DAY_CONTRAST;
int     lastContrast = -1;

// Player
struct Player {
  File     f;
  Header   h;
  size_t   fb = 0;
  uint16_t frame = 0;
  uint32_t nextFrameAt = 0;
  uint32_t slotEnd = 0;
  bool     loopDone = false;
  char     text[72] = "";          // LIVE info line (already converted to font codes)
  uint8_t  buf[FRAME_MAX];
  uint8_t  packed[PACKED_MAX];
} pl;

std::vector<String> playlist;
int  current = -1;
bool paused = false;
uint16_t defaultDuration = DEFAULT_DURATION_S;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
void reply(const char* fmt, ...) {
  Msg m;
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(m.s, sizeof(m.s), fmt, ap);
  va_end(ap);
  xQueueSend(replyQueue, &m, 0);
}

void flushReplies() {
  Msg m;
  while (xQueueReceive(replyQueue, &m, 0) == pdTRUE) {
    Serial.printf("%8lu > %s\n", (unsigned long)millis(), m.s);
    if (connected && statusChr) {
      statusChr->setValue((uint8_t*)m.s, strlen(m.s));
      statusChr->notify();
      delay(5);
    }
  }
}

void rxRelease() {
  portENTER_CRITICAL(&rxMux);
  rxClosed = true;
  uint8_t* p = rxBuf;
  rxBuf = nullptr;
  rxLen = 0;
  rxExpected = 0;
  rxOverflow = false;
  portEXIT_CRITICAL(&rxMux);
  donePending = false;
  if (p) free(p);
}

String pathOf(const String& name) { return String(SCREEN_DIR) + "/" + name; }

bool localTime(struct tm& t) {
  if (!timeKnown) return false;
  time_t now = time(nullptr) + utcOffset;
  gmtime_r(&now, &t);
  return true;
}

void updateContrast() {
  struct tm t;
  bool night = localTime(t) && t.tm_hour >= NIGHT_START && t.tm_hour < NIGHT_END;
  int k = night ? NIGHT_CONTRAST : dayContrast;
  if (k != lastContrast) {
    display.ssd1306_command(SSD1306_SETCONTRAST);
    display.ssd1306_command((uint8_t)k);
    lastContrast = k;
  }
}

// ---------------------------------------------------------------------------
// Drawing
// ---------------------------------------------------------------------------
void centerText(const char* s, int y, uint8_t size = 1) {
  display.setFont(nullptr);
  display.setTextSize(size);
  int16_t x1, y1;
  uint16_t w, h;
  display.getTextBounds(s, 0, y, &x1, &y1, &w, &h);
  display.setCursor((SCREEN_W - (int)w) / 2, y);
  display.print(s);
}

// FontText, centred, baseline at y (text must already be converted with toFontCodes)
void centerFontText(const char* coded, int baseline) {
  display.setFont(&FontText);
  display.setTextSize(1);
  display.setCursor((SCREEN_W - textWidth(&FontText, coded)) / 2, baseline);
  display.print(coded);
  display.setFont(nullptr);
}

static const char* MONTHS_EN[] = {"January", "February", "March", "April", "May", "June", "July",
                                  "August", "September", "October", "November", "December"};
static const char* DAYS_EN_SHORT[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
static const char* MONTHS_TR[] = {"Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
                                  "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"};
static const char* DAYS_TR[] = {"Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"};

// Same layout as clock_preview() in generator/screens.py
void drawClock(const char* infoCoded, uint8_t lang) {
  struct tm t;
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  if (!localTime(t)) {
    centerText("No time", 20, 2);
    centerText("sync from phone", 44);
    display.display();
    return;
  }
  char raw[48], coded[48];
  if (lang == LANG_TR) snprintf(raw, sizeof(raw), "%d %s %s", t.tm_mday, MONTHS_TR[t.tm_mon], DAYS_TR[t.tm_wday]);
  else snprintf(raw, sizeof(raw), "%s %d %s", DAYS_EN_SHORT[t.tm_wday], t.tm_mday, MONTHS_EN[t.tm_mon]);
  toFontCodes(raw, coded, sizeof(coded));
  centerFontText(coded, 8);

  char hm[6];
  snprintf(hm, sizeof(hm), "%02d%c%02d", t.tm_hour, (t.tm_sec % 2 == 0) ? ':' : ' ', t.tm_min);
  display.setFont(&FontClock);
  display.setCursor((SCREEN_W - textWidth(&FontClock, hm)) / 2, 42);
  display.print(hm);
  display.setFont(nullptr);

  for (int x = 14; x <= 114; x += 2) display.drawPixel(x, 47, SSD1306_WHITE);
  if (t.tm_sec) display.fillRect(14, 46, (100 * t.tm_sec + 29) / 59 + 1, 2, SSD1306_WHITE);

  if (infoCoded && *infoCoded) centerFontText(infoCoded, 62);
  display.display();
}

void idleStep() {
  static uint32_t last = 0;
  static float x = 10, y = 50, vx = 1.6f, vy = 1.1f;
  if (millis() - last < 33) return;
  last = millis();

  x += vx; y += vy;
  if (x < 3 || x > SCREEN_W - 4) vx = -vx;
  if (y < 42 || y > SCREEN_H - 4) vy = -vy;

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  centerText("ESP_Buddy v" FW_VERSION, 0);
  centerText(connected ? "BLE: connected" : "BLE: waiting", 11);
  struct tm t;
  if (localTime(t)) {
    char s[16];
    snprintf(s, sizeof(s), "%02d:%02d:%02d", t.tm_hour, t.tm_min, t.tm_sec);
    centerText(s, 22);
  } else {
    centerText("No content yet", 22);
  }
  display.drawFastHLine(0, 36, SCREEN_W, SSD1306_WHITE);
  display.fillCircle((int)x, (int)y, 3, SSD1306_WHITE);
  display.display();
}

void drawReceiving() {
  static uint32_t last = 0;
  if (millis() - last < 100) return;
  last = millis();

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  centerText("Receiving", 0, 2);
  size_t total = rxExpected, len = rxLen;      // read once: the BLE task may change them
  if (!rxClosed && total > 0) {
    centerText(rxName, 22);
    int filled = (int)((uint64_t)(SCREEN_W - 4) * (len > total ? total : len) / total);
    display.drawRect(0, 34, SCREEN_W, 10, SSD1306_WHITE);
    display.fillRect(2, 36, filled, 6, SSD1306_WHITE);
    char s[32];
    snprintf(s, sizeof(s), "%u / %u", (unsigned)len, (unsigned)total);
    centerText(s, 48);
  } else {
    char s[32];
    snprintf(s, sizeof(s), "%d files received", receivedCount);
    centerText(s, 30);
  }
  display.display();
}

// ---------------------------------------------------------------------------
// Player
// ---------------------------------------------------------------------------
void playerClose() {
  if (pl.f) pl.f.close();
}

// Names of the screen files, sorted (play order = name order)
std::vector<String> fileNames() {
  std::vector<String> v;
  File dir = LittleFS.open(SCREEN_DIR);
  if (dir && dir.isDirectory()) {
    File f = dir.openNextFile();
    while (f) {
      String name = f.name();
      int k = name.lastIndexOf('/');
      if (k >= 0) name = name.substring(k + 1);
      if (!f.isDirectory() && name.length() && name[0] != '.') v.push_back(name);
      f.close();
      f = dir.openNextFile();
    }
  }
  std::sort(v.begin(), v.end(), [](const String& a, const String& b) { return a < b; });
  return v;
}

void loadPlaylist() {
  playerClose();
  playlist = fileNames();
  Serial.printf("Playlist: %u screens\n", (unsigned)playlist.size());
}

// Checks that the OLB frame sizes in a stored file add up
static bool framesConsistent(File& f, const Header& h) {
  size_t fb = frameBytes(h.w, h.h), i = HEADER, n = f.size();
  for (uint16_t k = 0; k < h.frames; k++) {
    if (h.flags & FLAG_PACKBITS) {
      uint8_t g[4];
      if (!f.seek(i) || f.read(g, 4) != 4) return false;
      size_t len = le16(g + 2);
      if (len > PACKED_MAX) return false;
      i += 4 + len;
    } else {
      i += 2 + fb;
    }
    if (i > n) return false;
  }
  return i == n && f.seek(HEADER);
}

bool openScreen(int i) {
  playerClose();
  pl.f = LittleFS.open(pathOf(playlist[i]), "r");
  if (!pl.f) return false;
  uint8_t head[HEADER];
  bool ok = pl.f.read(head, HEADER) == HEADER && parseHeader(head, pl.h);
  if (ok && pl.h.kind == KIND_OLB) ok = framesConsistent(pl.f, pl.h);
  if (ok && pl.h.kind == KIND_LIVE) {
    if (!timeKnown) { pl.f.close(); return false; }    // skip the clock until the time is synced
    char raw[72] = "";
    size_t n = pl.h.textLen < sizeof(raw) - 1 ? pl.h.textLen : sizeof(raw) - 1;
    ok = pl.f.read((uint8_t*)raw, n) == n;
    raw[n] = 0;
    toFontCodes(raw, pl.text, sizeof(pl.text));
  }
  if (!ok) {
    Serial.printf("Invalid file: %s\n", playlist[i].c_str());
    pl.f.close();
    return false;
  }
  pl.fb = pl.h.kind == KIND_OLB ? frameBytes(pl.h.w, pl.h.h) : 0;
  pl.frame = 0;
  pl.loopDone = pl.h.kind == KIND_LIVE;
  uint32_t now = millis();
  pl.nextFrameAt = now;
  pl.slotEnd = now + 1000u * (pl.h.duration ? pl.h.duration : defaultDuration);
  Serial.printf("Screen %d/%u: %s\n", i + 1, (unsigned)playlist.size(), playlist[i].c_str());
  return true;
}

void step(int dir) {
  int n = (int)playlist.size();
  for (int attempt = 0; attempt < n; attempt++) {
    current = ((current + dir) % n + n) % n;
    if (openScreen(current)) return;
  }
  playerClose();          // nothing playable -> idle screen
  current = -1;
}

bool readFrame() {
  uint8_t g[4];
  if (pl.h.flags & FLAG_PACKBITS) {
    if (pl.f.read(g, 4) != 4) return false;
    size_t len = le16(g + 2);
    if (len > PACKED_MAX || pl.f.read(pl.packed, len) != len) return false;
    if (!unpackbits(pl.packed, len, pl.buf, pl.fb)) return false;
  } else {
    if (pl.f.read(g, 2) != 2 || pl.f.read(pl.buf, pl.fb) != pl.fb) return false;
  }
  uint16_t delayMs = le16(g);
  pl.nextFrameAt = millis() + (pl.h.frames == 1 ? 100 : (delayMs < 20 ? 20 : delayMs));
  return true;
}

void playerStep() {
  if (playlist.empty() || !pl.f) { idleStep(); return; }

  uint32_t now = millis();
  if ((int32_t)(now - pl.nextFrameAt) < 0) return;

  if (pl.loopDone && !paused && (int32_t)(now - pl.slotEnd) >= 0) {
    step(+1);
    return;
  }

  if (pl.h.kind == KIND_LIVE) {                  // live clock: redraw at 4 Hz
    drawClock(pl.text, pl.h.lang);
    pl.nextFrameAt = now + 250;
    return;
  }
  if (pl.h.frames == 1 && pl.frame > 0) {        // static screen already drawn
    pl.nextFrameAt = now + 100;
    return;
  }
  if (pl.frame >= pl.h.frames) {                 // animation rewinds
    pl.frame = 0;
    pl.loopDone = false;
    pl.f.seek(HEADER);
  }
  if (!readFrame()) {
    step(+1);
    return;
  }
  display.clearDisplay();
  display.drawBitmap((SCREEN_W - pl.h.w) / 2, (SCREEN_H - pl.h.h) / 2, pl.buf, pl.h.w, pl.h.h, SSD1306_WHITE);
  display.display();

  pl.frame++;
  if (pl.frame >= pl.h.frames) pl.loopDone = true;
}

void startPlaying() {
  receiving = false;
  loadPlaylist();
  current = -1;
  step(+1);
}

// ---------------------------------------------------------------------------
// Demo content (offline test: DEMO command)
// ---------------------------------------------------------------------------
bool writeOlb(const char* name, uint8_t w, uint8_t h, uint16_t frames, uint16_t duration,
              void (*draw)(GFXcanvas1&, int), uint16_t delayMs) {
  File f = LittleFS.open(pathOf(name), "w");
  if (!f) return false;
  uint8_t head[HEADER] = {'O', 'L', 'B', '1', w, h,
                          (uint8_t)(frames & 0xFF), (uint8_t)(frames >> 8),
                          (uint8_t)(duration & 0xFF), (uint8_t)(duration >> 8), 0};
  f.write(head, HEADER);
  GFXcanvas1 canvas(w, h);
  for (int i = 0; i < frames; i++) {
    canvas.fillScreen(0);
    draw(canvas, i);
    uint8_t g[2] = {(uint8_t)(delayMs & 0xFF), (uint8_t)(delayMs >> 8)};
    f.write(g, 2);
    f.write(canvas.getBuffer(), frameBytes(w, h));
  }
  f.close();
  return true;
}

bool writeLive(const char* name, uint16_t duration, uint8_t lang, const char* text) {
  File f = LittleFS.open(pathOf(name), "w");
  if (!f) return false;
  size_t n = strlen(text);
  uint8_t head[HEADER] = {'L', 'I', 'V', '1', LIVE_CLOCK, lang, 0, 0,
                          (uint8_t)(duration & 0xFF), (uint8_t)(duration >> 8),
                          (uint8_t)(n & 0xFF), (uint8_t)(n >> 8)};
  f.write(head, HEADER);
  f.write((const uint8_t*)text, n);
  f.close();
  return true;
}

void demoStatic(GFXcanvas1& c, int) {
  c.drawRect(0, 0, c.width(), c.height(), 1);
  c.setTextColor(1);
  c.setTextSize(2);
  c.setCursor(28, 8);
  c.print("DEMO");
  c.setTextSize(1);
  c.setCursor(10, 32);
  c.print("Static screen, 4 s");
  c.setCursor(10, 46);
  c.print("Animation next");
}

void demoBall(GFXcanvas1& c, int i) {
  int y = 8 + (int)(28.0f * fabsf(sinf(i * 3.14159f / 16.0f)));
  c.drawFastHLine(0, 47, 48, 1);
  c.fillCircle(24, 47 - y, 6, 1);
}

void demoSpinner(GFXcanvas1& c, int i) {
  float a = i * 3.14159f / 12.0f;
  c.drawLine(64, 32, 64 + (int)(28 * cosf(a)), 32 + (int)(28 * sinf(a)), 1);
  c.drawCircle(64, 32, 29, 1);
  c.setTextColor(1);
  c.setCursor(0, 0);
  c.print(i + 1);
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------
// FILE allocates the receive buffer; the page sends data only after the READY reply.
void fileStart(const char* arg) {
  char name[32];
  unsigned long size = 0, crc = 0;
  if (sscanf(arg, "%31s %lu %lx", name, &size, &crc) != 3) { reply("ERR FILE syntax"); return; }
  if (!validName(name)) { reply("ERR FILE name"); return; }
  if (size < HEADER || size > MAX_FILE) { reply("ERR FILE size %lu", size); return; }
  rxRelease();
  uint8_t* p = (uint8_t*)malloc(size);
  if (!p) { reply("ERR FILE memory"); return; }
  strncpy(rxName, name, sizeof(rxName));
  rxCrc = (uint32_t)crc;
  rxLen = 0;
  rxExpected = size;
  rxOverflow = false;
  rxBuf = p;
  rxClosed = false;
  receiving = true;
  lastRxActivity = millis();
  reply("READY %s", name);
}

void fileDone() {
  if (!rxBuf) { reply("ERR DONE no-file"); return; }
  rxClosed = true;
  size_t len = rxLen;
  if (rxOverflow || len != rxExpected) {
    reply("ERR DONE length %u/%u", (unsigned)len, (unsigned)rxExpected);
    rxRelease();
    return;
  }
  uint32_t c = crc32(rxBuf, len);
  if (c != rxCrc) {
    reply("ERR DONE crc %08lx", (unsigned long)c);
    rxRelease();
    return;
  }
  if (!validateFile(rxBuf, len)) {
    reply("ERR DONE format");
    rxRelease();
    return;
  }
  playerClose();
  String tmp = pathOf(".tmp");
  File f = LittleFS.open(tmp, "w");
  size_t written = f ? f.write(rxBuf, len) : 0;
  if (f) f.close();
  if (written != len) {
    LittleFS.remove(tmp);
    reply("ERR DONE space");
    rxRelease();
    return;
  }
  LittleFS.remove(pathOf(rxName));
  LittleFS.rename(tmp, pathOf(rxName));
  receivedCount++;
  reply("OK DONE %s", rxName);
  rxRelease();
}

int deleteAll() {
  playerClose();
  int n = 0;
  for (auto& name : fileNames()) if (LittleFS.remove(pathOf(name))) n++;
  LittleFS.remove(pathOf(".tmp"));
  playlist.clear();
  current = -1;
  return n;
}

void handleCommand(char* s) {
  Serial.printf("%8lu < %s\n", (unsigned long)millis(), s);

  char* arg = strchr(s, ' ');
  if (arg) { *arg++ = 0; while (*arg == ' ') arg++; } else arg = s + strlen(s);
  for (char* p = s; *p; p++) *p = toupper((unsigned char)*p);

  if (!strcmp(s, "FILE")) {                 // when typed in the Serial Monitor
    fileStart(arg);
  } else if (!strcmp(s, "DONE")) {
    lastRxActivity = millis();
    if (rxBuf && !rxOverflow && rxLen < rxExpected) {
      donePending = true;                 // data still arriving: finish when complete (max 3 s)
      doneDeadline = millis() + 3000;
    } else {
      fileDone();
    }
  } else if (!strcmp(s, "ABORT")) {
    rxRelease();
    reply("OK ABORT");
  } else if (!strcmp(s, "CLEAR")) {
    receiving = true;
    lastRxActivity = millis();
    receivedCount = 0;
    reply("OK CLEAR %d", deleteAll());
  } else if (!strcmp(s, "DELETE")) {
    if (!validName(arg)) { reply("ERR DELETE name"); return; }
    playerClose();
    bool ok = LittleFS.remove(pathOf(arg));
    startPlaying();
    reply(ok ? "OK DELETE %s" : "ERR DELETE missing %s", arg);
  } else if (!strcmp(s, "SHOW")) {
    rxRelease();
    startPlaying();
    reply("OK SHOW %u", (unsigned)playlist.size());
  } else if (!strcmp(s, "TIME")) {
    long long epoch = 0;
    long offsetMin = DEFAULT_OFFSET_MIN;
    if (sscanf(arg, "%lld %ld", &epoch, &offsetMin) < 1 || epoch < 1600000000LL) { reply("ERR TIME"); return; }
    struct timeval tv = {(time_t)epoch, 0};
    settimeofday(&tv, nullptr);
    utcOffset = (int32_t)offsetMin * 60;
    bool first = !timeKnown;
    timeKnown = true;
    lastContrast = -1;
    updateContrast();
    struct tm t;
    localTime(t);
    reply("OK TIME %02d:%02d:%02d", t.tm_hour, t.tm_min, t.tm_sec);
    if (first && !receiving) startPlaying();     // clock screens skipped so far are playable now
  } else if (!strcmp(s, "NEXT") || !strcmp(s, "PREV")) {
    if (receiving || playlist.empty()) { reply("ERR %s", s); return; }
    step(s[0] == 'N' ? +1 : -1);
    reply("OK %s %d", s, current + 1);
  } else if (!strcmp(s, "PAUSE")) {
    paused = true;
    reply("OK PAUSE");
  } else if (!strcmp(s, "RESUME")) {
    paused = false;
    reply("OK RESUME");
  } else if (!strcmp(s, "BRIGHTNESS")) {
    int v = constrain(atoi(arg), 0, 255);
    dayContrast = (uint8_t)v;
    lastContrast = -1;
    updateContrast();
    reply("OK BRIGHTNESS %d", v);
  } else if (!strcmp(s, "DURATION")) {
    int v = atoi(arg);
    if (v < 1 || v > 3600) { reply("ERR DURATION"); return; }
    defaultDuration = (uint16_t)v;
    reply("OK DURATION %d", v);
  } else if (!strcmp(s, "LIST")) {
    std::vector<String> names = fileNames();
    for (auto& name : names) {
      File f = LittleFS.open(pathOf(name), "r");
      reply("L %s %u", name.c_str(), f ? (unsigned)f.size() : 0u);
      if (f) f.close();
      flushReplies();
    }
    reply("OK LIST %u", (unsigned)names.size());
  } else if (!strcmp(s, "INFO")) {
    struct tm t;
    char clk[12] = "none";
    if (localTime(t)) snprintf(clk, sizeof(clk), "%02d:%02d", t.tm_hour, t.tm_min);
    reply("INFO v%s screens=%u at=%d time=%s fs=%u/%u heap=%u block=%u", FW_VERSION, (unsigned)playlist.size(), current + 1,
          clk, (unsigned)LittleFS.usedBytes(), (unsigned)LittleFS.totalBytes(), (unsigned)ESP.getFreeHeap(),
          (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT));
  } else if (!strcmp(s, "DEMO")) {
    deleteAll();
    bool ok = writeLive("00-clock.liv", 6, LANG_TR, "Demo: ğüşıöç İ 21°") &&
              writeOlb("01-demo.olb", 128, 64, 1, 4, demoStatic, 0) &&
              writeOlb("02-ball.olb", 48, 48, 16, 4, demoBall, 50) &&
              writeOlb("03-spinner.olb", 128, 64, 24, 3, demoSpinner, 60);
    startPlaying();
    reply(ok ? "OK DEMO %u" : "ERR DEMO", (unsigned)playlist.size());
  } else {
    reply("ERR unknown %s", s);
  }
}

// ---------------------------------------------------------------------------
// BLE
// ---------------------------------------------------------------------------
class ServerCB : public BLEServerCallbacks {
  void onConnect(BLEServer*) override {
    connected = true;
  }
  void onDisconnect(BLEServer*) override {
    connected = false;
    advertisePending = true;
    advertiseAt = millis() + 300;
  }
};

class CommandCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    Msg m;
    size_t n = c->getLength();
    if (n >= sizeof(m.s)) n = sizeof(m.s) - 1;
    memcpy(m.s, c->getData(), n);
    m.s[n] = 0;
    while (n && (m.s[n - 1] == '\r' || m.s[n - 1] == '\n' || m.s[n - 1] == ' ')) m.s[--n] = 0;
    if (!n) return;
    xQueueSend(commandQueue, &m, 0);
  }
};

class DataCB : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* c) override {
    size_t n = c->getLength();
    const uint8_t* src = c->getData();
    portENTER_CRITICAL(&rxMux);
    if (rxBuf && !rxClosed) {
      if (rxLen + n > rxExpected) rxOverflow = true;
      else { memcpy(rxBuf + rxLen, src, n); rxLen += n; }
    }
    portEXIT_CRITICAL(&rxMux);
    lastRxActivity = millis();
  }
};

void bleStart() {
  BLEDevice::init(BLE_NAME);
  BLEDevice::setMTU(517);
  server = BLEDevice::createServer();
  server->setCallbacks(new ServerCB());

  BLEService* service = server->createService(SERVICE_UUID);

  BLECharacteristic* command = service->createCharacteristic(COMMAND_UUID, BLECharacteristic::PROPERTY_WRITE);
  command->setCallbacks(new CommandCB());

  BLECharacteristic* dataChr = service->createCharacteristic(
      DATA_UUID, BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR);
  dataChr->setCallbacks(new DataCB());

  statusChr = service->createCharacteristic(
      STATUS_UUID, BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_READ);
  // CCCD (0x2902) for notifications. Newer cores may add it themselves; add it if missing.
  if (statusChr->getDescriptorByUUID(BLEUUID((uint16_t)0x2902)) == nullptr) {
    statusChr->addDescriptor(new BLE2902());
  }

  service->start();
  BLEAdvertising* adv = BLEDevice::getAdvertising();
  adv->addServiceUUID(SERVICE_UUID);
  adv->setScanResponse(true);
  adv->setMinPreferred(0x06);   // recommended interval for iPhone connections
  adv->setMinPreferred(0x12);
  BLEDevice::startAdvertising();
  Serial.println("BLE advertising: " BLE_NAME);
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\nESP_Buddy v" FW_VERSION);

  commandQueue = xQueueCreate(8, sizeof(Msg));
  replyQueue = xQueueCreate(16, sizeof(Msg));

  Wire.begin(OLED_SDA, OLED_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS, true, false)) {
    Serial.println("OLED not found! Check the wiring and the address (0x3C/0x3D).");
  }
  updateContrast();
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  centerText("ESP_Buddy", 16, 2);
  centerText("v" FW_VERSION, 40);
  display.display();

  if (!LittleFS.begin(true)) Serial.println("LittleFS could not be mounted!");
  LittleFS.mkdir(SCREEN_DIR);

  bleStart();
  delay(800);
  startPlaying();
}

void loop() {
  // Commands from the Serial Monitor (for testing): set the line ending to "Newline"
  static char line[MSG_MAX];
  static size_t ln = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (ln) { line[ln] = 0; Msg m; strcpy(m.s, line); xQueueSend(commandQueue, &m, 0); ln = 0; }
    } else if (ln < sizeof(line) - 1) {
      line[ln++] = c;
    }
  }

  Msg m;
  while (xQueueReceive(commandQueue, &m, 0) == pdTRUE) handleCommand(m.s);

  // Progress notifications
  static size_t lastReported = 0;
  if (!rxClosed && rxBuf) {
    size_t len = rxLen;
    if (len < lastReported) lastReported = 0;
    if (len - lastReported >= PROGRESS_STEP || (len == rxExpected && len != lastReported)) {
      lastReported = len;
      reply("PROGRESS %u", (unsigned)len);
    }
  } else {
    lastReported = 0;
  }

  if (donePending && (rxLen >= rxExpected || rxOverflow || (int32_t)(millis() - doneDeadline) >= 0)) {
    donePending = false;
    fileDone();
  }

  // Link lost: drop the half-received file and go back to playing
  static bool wasConnected = false;
  if (wasConnected && !connected) {
    Serial.println("BLE disconnected");
    rxRelease();
    if (receiving) startPlaying();
  }
  if (!wasConnected && connected) Serial.println("BLE connected");
  wasConnected = connected;

  if (advertisePending && (int32_t)(millis() - advertiseAt) >= 0) {
    advertisePending = false;
    BLEDevice::startAdvertising();
  }

  static uint32_t lastContrastCheck = 0;
  if (millis() - lastContrastCheck > 5000) { lastContrastCheck = millis(); updateContrast(); }

  if (receiving && (uint32_t)(millis() - lastRxActivity) > RECEIVE_TIMEOUT_MS) {
    Serial.println("Receive timeout, back to playing");
    rxRelease();
    startPlaying();
  }

  if (receiving) {
    if (pl.f) playerClose();
    drawReceiving();
  } else {
    playerStep();
  }

  flushReplies();
  delay(2);
}
