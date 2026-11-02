# ESP_Buddy screens

Edit this file on GitHub and commit; the next Actions run regenerates the screens accordingly.

- `[x]` = show the screen, `[ ]` = hide it.
- The order of the lines is the rotation order on the device. A screen may appear more than once (e.g. `clock`, `face`).
- Every `face` line gets a different mood, picked from the day's data (see README).
- Line format: `- [x] id | description` — keep the id, write whatever you like as the description.
- Every screen is generated in English and Turkish; the language is chosen on the web page when sending.

## Settings
- city: Ankara
- lat: 39.93
- lon: 32.86
- duration: 7

`duration` = how many seconds static screens stay on. Animations and multi-page text use their own timing.

## Rotation
- [x] clock | Live clock — drawn by the device, synced from the phone
- [x] weather_now | Weather now, animated icon
- [x] face | Face animation
- [x] usd | USD/TRY, large + 30-day chart
- [x] clock | Live clock
- [x] weather_hourly | Next 12 hours: temperature curve and chance of rain
- [x] markets | EUR/TRY, gold per gram, BTC, CBRT (Turkish central bank) USD rate
- [x] face | Face animation
- [x] clock | Live clock
- [x] weather_3day | 3-day forecast
- [x] sun_moon | Sunrise/sunset and moon phase
- [x] face | Face animation
- [x] clock | Live clock
- [x] air_quality | Air quality (European AQI, PM2.5, PM10)
- [x] earthquake | Largest earthquake of the last 24 h on a map (Kandilli)
- [x] holiday | Days until the next public holiday in Turkey
- [x] face | Face animation
- [x] on_this_day | Wikipedia: on this day
- [x] quote | Quote of the day (English)
- [x] screensaver | Screensaver: Game of Life / starfield / Matrix (one per day)
