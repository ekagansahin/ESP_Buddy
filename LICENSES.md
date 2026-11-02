# Third-party licenses

The BDF pixel fonts in `generator/fonts/` were made from the copies in the [u8g2](https://github.com/olikraus/u8g2) repository (`tools/font/bdf`), keeping only the characters needed for English and Turkish (`tools/prepare_fonts.py`). The firmware's `font_text.h` and `font_clock.h` were generated from the same fonts.

| File | Source | License |
|---|---|---|
| `4x6`, `5x8`, `6x10`, `6x13B`, `7x14B`, `10x20` | X11 misc-fixed (ISO 10646 extension by Markus Kuhn) | Public domain ("Public domain font. Share and enjoy.") |
| `helvB10`…`helvB24` | X11 Adobe 75dpi Helvetica Bold | © 1984, 1987 Adobe Systems Inc., © 1988, 1991 Digital Equipment Corp. Distributed with X under its permission notice; the copyright notices are kept inside the files. "Helvetica" is a trademark of Linotype. |
| `spleen-16x32` | [Spleen](https://github.com/fcambus/spleen) by Frederic Cambus | BSD 2-Clause (below) |

## Spleen — BSD 2-Clause License

```
Copyright (c) 2018-2022, Frederic Cambus
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

  * Redistributions of source code must retain the above copyright
    notice, this list of conditions and the following disclaimer.

  * Redistributions in binary form must reproduce the above copyright
    notice, this list of conditions and the following disclaimer in the
    documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```

## Data sources

Open-Meteo (CC BY 4.0), Yahoo Finance (unofficial endpoint), fawazahmed0/exchange-api, Frankfurter (ECB), CBRT/TCMB, Truncgil Finans (unofficial), CoinGecko, Kandilli Observatory (via the api.orhanaydogdu.com.tr community API), Nager.Date, Wikipedia/Wikimedia (CC BY-SA), ZenQuotes. Each is subject to its own terms. For personal, non-commercial use.
