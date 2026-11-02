// ESP_Buddy — preview + Web Bluetooth sender + remote control
'use strict';

const SERVICE = '68961d5e-4b75-4893-bb3e-14ce93b54693';
const COMMAND = '0c3fb439-03a5-4085-ad4e-c2975815cf1a';
const DATA = 'c34519c8-f6e2-4dba-9be7-f5591b429020';
const STATUS = 'ae53dc3e-1ba9-4f77-b87c-428aa72328e8';
const CHUNK = 180;                // iPhone MTU 185 -> 182 bytes; safe everywhere that matters
const OLED = [223, 243, 255];

// ---------------------------------------------------------------- texts
const TEXT = {
  en: {
    notConnected: 'not connected', connected: 'connected',
    connectSend: 'Connect & send', connectOnly: 'Connect only', disconnect: 'Disconnect',
    syncTime: '⏱ Time', prev: 'Previous screen', pause: 'Pause / resume', next: 'Next screen',
    screens: 'Screens', all: 'All', none: 'None',
    moodsSources: "Today's faces and data sources", log: 'Log',
    footer: 'iPhone: Safari and Chrome cannot use Bluetooth — open this page in <b>Bluefy</b>. On a computer, Chrome or Edge works.',
    loading: 'loading…', data: 'Data', justNow: 'just now', hoursAgo: (h) => `${h} h ago`,
    noManifest: 'Could not load the screen list. Has the GitHub Actions workflow run at least once?',
    sampleWarn: 'This build was generated from <b>sample data</b>.',
    staleWarn: (h) => `The data is ${h} hours old; GitHub's scheduled runs may be delayed.`,
    noBle: 'This browser has no Web Bluetooth. On iPhone open the page in <b>Bluefy</b>; on a computer use Chrome or Edge.',
    selected: (n, size, sec) => `Selected: ${n} screens · ${size} · about ${sec} s to send · language: English`,
    frames: (n) => (n === 1 ? '1 frame' : `${n} frames`), pickOne: 'Select at least one screen first', connecting: 'Connecting…',
    timeSynced: 'Time synced: ', sending: (i, n, t) => `Sending ${i}/${n}: ${t}`,
    done: (n, size, sec, speed) => `Done: ${n} screens, ${size} · ${sec} s (${speed}/s)`,
    noDevice: 'No device selected', error: 'Error: ', skipped: 'Skipped: ', linkLost: 'connection lost',
    attempt: (a) => `attempt ${a}/3`,
  },
  tr: {
    notConnected: 'bağlı değil', connected: 'bağlı',
    connectSend: 'Bağlan ve gönder', connectOnly: 'Sadece bağlan', disconnect: 'Bağlantıyı kes',
    syncTime: '⏱ Saat', prev: 'Önceki ekran', pause: 'Dur / devam', next: 'Sonraki ekran',
    screens: 'Ekranlar', all: 'Hepsi', none: 'Hiçbiri',
    moodsSources: 'Bugünün yüzleri ve veri kaynakları', log: 'Kayıt',
    footer: 'iPhone: Safari ve Chrome Bluetooth kullanamaz — bu sayfayı <b>Bluefy</b> ile açın. Bilgisayarda Chrome veya Edge çalışır.',
    loading: 'yükleniyor…', data: 'Veri', justNow: 'az önce', hoursAgo: (h) => `${h} saat önce`,
    noManifest: 'Ekran listesi yüklenemedi. GitHub Actions en az bir kez çalıştı mı?',
    sampleWarn: 'Bu yayın <b>örnek veriyle</b> üretildi.',
    staleWarn: (h) => `Veri ${h} saat önce üretilmiş; GitHub zamanlaması gecikiyor olabilir.`,
    noBle: 'Bu tarayıcıda Web Bluetooth yok. iPhone\'da sayfayı <b>Bluefy</b> ile açın; bilgisayarda Chrome/Edge kullanın.',
    selected: (n, size, sec) => `Seçili: ${n} ekran · ${size} · tahmini ${sec} sn aktarım · dil: Türkçe`,
    frames: (n) => `${n} kare`, pickOne: 'Önce en az bir ekran seç', connecting: 'Bağlanıyor…',
    timeSynced: 'Saat eşitlendi: ', sending: (i, n, t) => `Gönderiliyor ${i}/${n}: ${t}`,
    done: (n, size, sec, speed) => `Tamam: ${n} ekran, ${size} · ${sec} sn (${speed}/sn)`,
    noDevice: 'Cihaz seçilmedi', error: 'Hata: ', skipped: 'Atlanan: ', linkLost: 'bağlantı koptu',
    attempt: (a) => `deneme ${a}/3`,
  },
};

const $ = (id) => document.getElementById(id);
const enc = new TextEncoder();
const dec = new TextDecoder();

function store(key, value) {
  try {
    if (value === undefined) return JSON.parse(localStorage.getItem(key));
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) { return null; }
}

let lang = store('lang') || ((navigator.language || '').toLowerCase().startsWith('tr') ? 'tr' : 'en');
const t = (k) => TEXT[lang][k];

function applyTexts() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-t]').forEach((el) => { el.innerHTML = t(el.dataset.t); });
  document.querySelectorAll('[data-title]').forEach((el) => { el.title = t(el.dataset.title); });
  document.querySelectorAll('.lang button').forEach((b) => b.classList.toggle('on', b.dataset.lang === lang));
  showLink(device && device.gatt.connected);
}

// ---------------------------------------------------------------- helpers
function log(s) {
  const z = new Date().toLocaleTimeString(lang === 'tr' ? 'tr-TR' : 'en-GB');
  const el = $('log');
  el.textContent = `${z}  ${s}\n` + el.textContent.slice(0, 20000);
}
function status(s) { $('status').textContent = s; }
function warn(s) { const w = $('warning'); w.innerHTML = s; w.classList.toggle('hidden', !s); }
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
function kb(n) { return n < 1024 ? `${n} B` : `${(n / 1024).toFixed(1)} KB`; }

const CRC_TABLE = (() => {
  const tb = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
    tb[n] = c >>> 0;
  }
  return tb;
})();
function crc32(b) {
  let c = 0xFFFFFFFF;
  for (let i = 0; i < b.length; i++) c = CRC_TABLE[(c ^ b[i]) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

// ---------------------------------------------------------------- .olb decoder
function unpackbits(src, len) {
  const out = new Uint8Array(len);
  let i = 0, o = 0;
  while (i < src.length && o < len) {
    const h = src[i++];
    if (h < 128) { out.set(src.subarray(i, i + h + 1), o); i += h + 1; o += h + 1; }
    else if (h > 128) { out.fill(src[i++], o, o + 257 - h); o += 257 - h; }
  }
  return out;
}
function olbDecode(b) {
  if (String.fromCharCode(...b.subarray(0, 4)) !== 'OLB1') throw new Error('not an OLB file');
  const v = new DataView(b.buffer, b.byteOffset, b.byteLength);
  const w = b[4], h = b[5], n = v.getUint16(6, true), duration = v.getUint16(8, true), flags = b[10];
  const fb = ((w + 7) >> 3) * h;
  const frames = [];
  let i = 16;
  for (let k = 0; k < n; k++) {
    const ms = v.getUint16(i, true); i += 2;
    let px;
    if (flags & 1) { const ln = v.getUint16(i, true); i += 2; px = unpackbits(b.subarray(i, i + ln), fb); i += ln; }
    else { px = b.subarray(i, i + fb); i += fb; }
    frames.push({ ms, px });
  }
  return { w, h, duration, frames };
}
function drawFrame(ctx, an, px) {
  const img = ctx.createImageData(128, 64);
  const ox = (128 - an.w) >> 1, oy = (64 - an.h) >> 1, rb = (an.w + 7) >> 3;
  for (let y = 0; y < an.h; y++) {
    for (let x = 0; x < an.w; x++) {
      if (px[y * rb + (x >> 3)] & (0x80 >> (x & 7))) {
        const p = ((y + oy) * 128 + x + ox) * 4;
        img.data[p] = OLED[0]; img.data[p + 1] = OLED[1]; img.data[p + 2] = OLED[2];
      }
    }
  }
  for (let p = 3; p < img.data.length; p += 4) img.data[p] = 255;
  ctx.putImageData(img, 0, 0);
}

// ---------------------------------------------------------------- preview
let manifest = null;
let cards = [];         // {e, raw, an, ctx, k, nextAt, visible, box, card}
let loadId = 0;
let observer = null;

async function load() {
  const my = ++loadId;
  cards = [];
  $('grid').innerHTML = '';
  $('dataTime').textContent = t('loading');
  try {
    const r = await fetch(`${lang}/manifest.json?t=${Date.now()}`, { cache: 'no-store' });
    manifest = await r.json();
  } catch (e) {
    $('dataTime').textContent = 'manifest.json?';
    warn(t('noManifest'));
    return;
  }
  if (my !== loadId) return;
  const gen = new Date(manifest.generated);
  const hours = (Date.now() - gen.getTime()) / 3600e3;
  const locale = lang === 'tr' ? 'tr-TR' : 'en-GB';
  $('dataTime').textContent = `${t('data')}: ${gen.toLocaleString(locale, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}` +
    ` · ${hours < 1 ? t('justNow') : t('hoursAgo')(Math.round(hours))}`;
  const warnings = [];
  if (manifest.sample) warnings.push(t('sampleWarn'));
  if (hours > 12) warnings.push(t('staleWarn')(Math.round(hours)));
  if (!navigator.bluetooth) warnings.push(t('noBle'));
  warn(warnings.join('<br>'));

  const off = new Set(store('off') || []);
  const ver = encodeURIComponent(manifest.generated);
  const grid = $('grid');
  if (observer) observer.disconnect();
  observer = new IntersectionObserver((list) => list.forEach((x) => {
    const c = cards.find((s) => s && s.card === x.target);
    if (c) c.visible = x.isIntersecting;
  }));
  await Promise.all(manifest.screens.map(async (e, i) => {
    const card = document.createElement('div');
    card.className = 'screen';
    card.innerHTML = `<canvas width="128" height="64"></canvas>
      <label class="info"><input type="checkbox"><span><div class="name"></div><div class="sub"></div></span></label>`;
    card.querySelector('.name').textContent = `${String(i + 1).padStart(2, '0')} · ${e.title}`;
    card.querySelector('.sub').textContent = [e.note, `${kb(e.bytes)} · ${t('frames')(e.frames)}`].filter(Boolean).join(' · ');
    const box = card.querySelector('input');
    box.checked = !off.has(e.file.slice(3));
    card.classList.toggle('off', !box.checked);
    box.addEventListener('change', () => { card.classList.toggle('off', !box.checked); saveSelection(); summary(); });
    grid.appendChild(card);
    const c = { e, card, box, ctx: card.querySelector('canvas').getContext('2d'), k: 0, nextAt: 0, visible: true };
    cards[i] = c;
    observer.observe(card);
    const [raw, prev] = await Promise.all([
      fetch(`${lang}/screens/${e.file}?v=${ver}`).then((r) => r.arrayBuffer()).then((a) => new Uint8Array(a)),
      fetch(`${lang}/${e.preview}?v=${ver}`).then((r) => r.arrayBuffer()).then((a) => new Uint8Array(a)),
    ]);
    if (my !== loadId) return;
    c.raw = raw;
    c.an = olbDecode(prev);
    drawFrame(c.ctx, c.an, c.an.frames[0].px);
  }));
  if (my !== loadId) return;
  showMoods();
  summary();
}

function animate(now) {
  for (const s of cards) {
    if (!s || !s.an || !s.visible || s.an.frames.length < 2 || now < s.nextAt) continue;
    s.k = (s.k + 1) % s.an.frames.length;
    const f = s.an.frames[s.k];
    drawFrame(s.ctx, s.an, f.px);
    s.nextAt = now + Math.max(20, f.ms);
  }
  requestAnimationFrame(animate);
}

function selected() { return cards.filter((s) => s && s.box.checked && s.raw); }
function saveSelection() {
  // remembered by screen id (file name without its number), shared by both languages
  const off = new Set(store('off') || []);
  cards.forEach((s) => { if (!s) return; const id = s.e.file.slice(3); if (s.box.checked) off.delete(id); else off.add(id); });
  store('off', [...off]);
}
function summary() {
  const s = selected();
  const total = s.reduce((a, x) => a + x.raw.length, 0);
  const speed = store('speed') || 6000;
  status(t('selected')(s.length, kb(total), Math.max(1, Math.round(total / speed))));
}
function showMoods() {
  const m = $('moods');
  m.innerHTML = '';
  for (const x of manifest.moods || []) {
    const el = document.createElement('div');
    el.textContent = `• ${x.name} — ${x.reason}`;
    m.appendChild(el);
  }
  const k = $('sources');
  k.innerHTML = '';
  for (const [name, st] of Object.entries(manifest.sources || {})) {
    const el = document.createElement('div');
    el.className = st === 'ok' ? 'ok' : 'bad';
    el.textContent = `${st === 'ok' ? '✓' : '✗'} ${name}${st === 'ok' ? '' : ' — ' + st.replace(/^error: /, '')}`;
    k.appendChild(el);
  }
  if (manifest.skipped && manifest.skipped.length) {
    const el = document.createElement('div');
    el.className = 'bad';
    el.textContent = t('skipped') + manifest.skipped.join(', ');
    k.appendChild(el);
  }
}

// ---------------------------------------------------------------- BLE
let device = null, chrCommand = null, chrData = null, chrStatus = null;
let waiters = [];
let busy = false;

function showLink(on) {
  const b = $('linkBadge');
  b.textContent = on ? t('connected') : t('notConnected');
  b.classList.toggle('on', !!on);
  $('remote').classList.toggle('off', !on);
  $('btnConnect').textContent = on ? t('disconnect') : t('connectOnly');
}

function onNotify(e) {
  const s = dec.decode(e.target.value);
  log('← ' + s);
  if (s.startsWith('PROGRESS')) return;
  const w = waiters[0];
  if (!w) return;
  if (w.re.test(s)) { waiters.shift(); w.ok(s); }
  else if (s.startsWith('ERR')) { waiters.shift(); w.no(new Error(s)); }
}

async function write(c, value, withResponse) {
  if (withResponse || !c.writeValueWithoutResponse) {
    return c.writeValueWithResponse ? c.writeValueWithResponse(value) : c.writeValue(value);
  }
  return c.writeValueWithoutResponse(value);
}

function command(text, re = /^OK/, ms = 10000) {
  return new Promise((ok, no) => {
    const w = { re, ok: (s) => { clearTimeout(z); ok(s); }, no: (e) => { clearTimeout(z); no(e); } };
    const z = setTimeout(() => { waiters = waiters.filter((x) => x !== w); no(new Error('timeout: ' + text)); }, ms);
    waiters.push(w);
    log('→ ' + text);
    write(chrCommand, enc.encode(text), true).catch((e) => { waiters = waiters.filter((x) => x !== w); clearTimeout(z); no(e); });
  });
}

async function connect() {
  if (!navigator.bluetooth) throw new Error(t('noBle').replace(/<[^>]+>/g, ''));
  if (device && device.gatt.connected) return;
  if (!device) {
    device = await navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: 'ESP_Buddy' }, { services: [SERVICE] }],
      optionalServices: [SERVICE],
    });
    device.addEventListener('gattserverdisconnected', () => {
      log(t('linkLost'));
      showLink(false);
      waiters.forEach((w) => w.no(new Error(t('linkLost'))));
      waiters = [];
    });
  }
  status(t('connecting'));
  const gatt = await device.gatt.connect();
  const svc = await gatt.getPrimaryService(SERVICE);
  chrCommand = await svc.getCharacteristic(COMMAND);
  chrData = await svc.getCharacteristic(DATA);
  chrStatus = await svc.getCharacteristic(STATUS);
  chrStatus.removeEventListener('characteristicvaluechanged', onNotify);
  chrStatus.addEventListener('characteristicvaluechanged', onNotify);
  await chrStatus.startNotifications();
  showLink(true);
  log('connected: ' + (device.name || 'ESP_Buddy'));
  await syncTime();
  try { status(await command('INFO', /^INFO/)); } catch (e) { log(e.message); }
}

async function syncTime() {
  const offset = -new Date().getTimezoneOffset();
  const s = await command(`TIME ${Math.floor(Date.now() / 1000)} ${offset}`, /^OK TIME/);
  status(t('timeSynced') + s.slice(8));
}

async function sendFile(name, b, progress) {
  const crc = crc32(b).toString(16).padStart(8, '0');
  let chunk = CHUNK;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const withResponse = attempt > 1;          // retries: slower but acknowledged writes
    try {
      await command(`FILE ${name} ${b.length} ${crc}`, /^READY/);
      for (let i = 0; i < b.length; i += chunk) {
        try {
          await write(chrData, b.subarray(i, Math.min(b.length, i + chunk)), withResponse);
        } catch (e) {
          // an acknowledged write failing too may mean the packet is too long (small MTU)
          if (withResponse && chunk > 20) { chunk = 20; throw new Error('chunk reduced to 20 bytes'); }
          throw e;
        }
        progress(Math.min(b.length, i + chunk));
      }
      await command('DONE', /^OK/, 15000);
      return;
    } catch (e) {
      log(`${name}: ${e.message} (${t('attempt')(attempt)})`);
      if (!device.gatt.connected) throw e;
      try { await command('ABORT'); } catch (_) { /* ignore */ }
      progress(0);
      if (attempt === 3) throw e;
      await sleep(300);
    }
  }
}

async function send() {
  const list = selected();
  if (!list.length) { status(t('pickOne')); return; }
  await connect();
  const total = list.reduce((a, x) => a + x.raw.length, 0);
  let doneBytes = 0;
  const bar = $('progressBar');
  $('progress').classList.remove('hidden');
  const start = performance.now();
  let ok = false;
  try {
    await command('CLEAR', /^OK CLEAR/);
    for (let i = 0; i < list.length; i++) {
      const { e, raw } = list[i];
      await sendFile(e.file, raw, (n) => {
        bar.style.width = `${((doneBytes + n) / total) * 100}%`;
        status(t('sending')(i + 1, list.length, e.title));
      });
      doneBytes += raw.length;
    }
    ok = true;
  } finally {
    // even after an error, never leave the device in receive mode: let it play what arrived
    if (device && device.gatt.connected) {
      const s = await command('SHOW', /^OK SHOW/).catch((e) => e.message);
      if (ok) {
        const sec = (performance.now() - start) / 1000;
        store('speed', Math.round(total / sec));
        status(`${t('done')(list.length, kb(total), sec.toFixed(1), kb(Math.round(total / sec)))} · ${s}`);
        bar.style.width = '100%';
      }
    }
  }
}

async function job(fn) {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button').forEach((b) => { b.disabled = true; });
  try { await fn(); } catch (e) {
    if (e.name === 'NotFoundError') status(t('noDevice'));
    else { status(t('error') + e.message); log('ERROR ' + e.message); }
  } finally {
    busy = false;
    document.querySelectorAll('button').forEach((b) => { b.disabled = false; });
  }
}

// ---------------------------------------------------------------- events
$('btnSend').addEventListener('click', () => job(send));
$('btnConnect').addEventListener('click', () => job(async () => {
  if (device && device.gatt.connected) { device.gatt.disconnect(); return; }
  await connect();
}));
$('btnTime').addEventListener('click', () => job(syncTime));
let paused = false;
document.querySelectorAll('#remote [data-cmd]').forEach((b) => b.addEventListener('click', () => job(async () => {
  let c = b.dataset.cmd;
  if (b.id === 'btnPause') c = paused ? 'RESUME' : 'PAUSE';
  status(await command(c));
  if (b.id === 'btnPause') { paused = !paused; b.textContent = paused ? '▶︎▶︎' : '❚❚'; }
})));
const bright = $('brightness');
bright.value = store('brightness') ?? 207;
bright.addEventListener('change', () => job(async () => {
  store('brightness', +bright.value);
  status(await command(`BRIGHTNESS ${bright.value}`));
}));
$('btnAll').addEventListener('click', () => { cards.forEach((s) => { s.box.checked = true; s.card.classList.remove('off'); }); saveSelection(); summary(); });
$('btnNone').addEventListener('click', () => { cards.forEach((s) => { s.box.checked = false; s.card.classList.add('off'); }); saveSelection(); summary(); });
document.querySelectorAll('.lang button').forEach((b) => b.addEventListener('click', () => {
  if (busy || b.dataset.lang === lang) return;
  lang = b.dataset.lang;
  store('lang', lang);
  applyTexts();
  load();
}));

applyTexts();
load();
requestAnimationFrame(animate);
