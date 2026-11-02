"""Reads BDF pixel fonts and draws them onto 1-bit PIL images (no anti-aliasing, Turkish letters included)."""
import os
from functools import lru_cache

from PIL import Image

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

REPLACE = {"“": '"', "”": '"', "„": '"', "’": "'", "‘": "'", " ": " ", "​": "", "–": "-", "—": "-"}


class Font:
    def __init__(self, path):
        self.glyphs = {}
        self.ascent = self.descent = 0
        with open(path, encoding="latin-1") as f:
            lines = f.read().splitlines()
        i = 0
        while i < len(lines):
            s = lines[i]
            if s.startswith("FONT_ASCENT"):
                self.ascent = int(s.split()[1])
            elif s.startswith("FONT_DESCENT"):
                self.descent = int(s.split()[1])
            elif s.startswith("STARTCHAR"):
                code = adv = None
                w = h = xo = yo = 0
                rows = []
                i += 1
                while not lines[i].startswith("ENDCHAR"):
                    p = lines[i].split()
                    if p[0] == "ENCODING":
                        code = int(p[1])
                    elif p[0] == "DWIDTH":
                        adv = int(p[1])
                    elif p[0] == "BBX":
                        w, h, xo, yo = map(int, p[1:5])
                    elif p[0] == "BITMAP":
                        i += 1
                        while not lines[i].startswith("ENDCHAR"):
                            rows.append(int(lines[i], 16) if lines[i] else 0)
                            i += 1
                        break
                    i += 1
                img = None
                if w and h:
                    img = Image.new("1", (w, h), 0)
                    px = img.load()
                    rb = (w + 7) // 8
                    for y, r in enumerate(rows[:h]):
                        for x in range(w):
                            if (r >> (rb * 8 - 1 - x)) & 1:
                                px[x, y] = 1
                self.glyphs[code] = (adv, w, h, xo, yo, img)
            i += 1
        self.height = self.ascent + self.descent

    def _glyph(self, ch):
        return self.glyphs.get(ord(ch)) or self.glyphs.get(ord("?"))

    def has(self, ch):
        return ord(ch) in self.glyphs

    @staticmethod
    def clean(s):
        return "".join(REPLACE.get(c, c) for c in str(s))

    def width(self, s):
        return sum(self._glyph(c)[0] for c in self.clean(s))

    def draw(self, img, x, y, s, color=1):
        """(x, y) = top-left of the line; the baseline is y + ascent. Returns the end x."""
        base = y + self.ascent
        for c in self.clean(s):
            adv, w, h, xo, yo, g = self._glyph(c)
            if g is not None:
                img.paste(color, (x + xo, base - yo - h), g)
            x += adv
        return x

    def center(self, img, y, s, color=1, x0=0, x1=None):
        x1 = img.width if x1 is None else x1
        return self.draw(img, x0 + (x1 - x0 - self.width(s)) // 2, y, s, color)

    def right(self, img, x_right, y, s, color=1):
        return self.draw(img, x_right - self.width(s), y, s, color)

    def wrap(self, s, width):
        """Word wrap; breaks words that do not fit on one line."""
        lines, cur = [], ""
        for word in self.clean(s).split():
            cand = (cur + " " + word).strip()
            if self.width(cand) <= width:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            while self.width(word) > width:
                k = len(word)
                while k > 1 and self.width(word[:k] + "-") > width:
                    k -= 1
                lines.append(word[:k] + "-")
                word = word[k:]
            cur = word
        if cur:
            lines.append(cur)
        return lines

    def ellipsize(self, s, width):
        s = self.clean(s)
        if self.width(s) <= width:
            return s
        while s and self.width(s + "…") > width:
            s = s[:-1]
        return s.rstrip() + "…"


@lru_cache(maxsize=None)
def font(name):
    return Font(os.path.join(FONT_DIR, name + ".bdf"))
