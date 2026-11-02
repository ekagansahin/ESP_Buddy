# Setup

Setup takes 15–20 minutes. Do it in this order: GitHub, then the ESP32, then the iPhone.

## 1. GitHub repository

1. On GitHub, click **New repository**.
   - Name: `ESP_Buddy`
   - Choose **Public**. On a free account, GitHub Pages only works for public repositories.
   - Do *not* add a README, .gitignore or license. Leave the repository empty.
2. Upload the contents of this folder (`esp_buddy_v2`). Either way works:

   **a) With git (recommended):**
   ```bash
   cd C:\Users\ekaga\Desktop\esp\esp_buddy_v2
   git init -b main
   git add .
   git commit -m "ESP_Buddy first version"
   git remote add origin https://github.com/ekagansahin/ESP_Buddy.git
   git push -u origin main
   ```

   **b) In the browser:**
   1. On the empty repository's page, click *uploading an existing file*.
   2. Drag in **everything inside** the `esp_buddy_v2` folder (including `.github`), not the folder itself.
   3. Click **Commit changes**.

   > `.github` may be hidden. In Windows Explorer turn on *View → Show → Hidden items*. Without this folder Actions will not run.

3. **Turn on Pages:** go to repository → **Settings → Pages → Build and deployment → Source** and choose **"GitHub Actions"**.
4. **Run the first build:** go to repository → **Actions**. If GitHub asks you to enable workflows, confirm. Then click **"Build screens and publish" → Run workflow**.
   - It takes about a minute. When it shows a green tick, the site is live at **https://ekagansahin.github.io/ESP_Buddy/**
   - The run started automatically by your push may have failed at *deploy*, because Pages was not on yet. That is expected; running it once by hand after step 3 fixes it.
   - The run's summary page lists the screens it generated and which APIs answered.
5. From now on the workflow runs by itself every 3 hours. GitHub sometimes starts scheduled runs hours late; the top of the web page shows how old the data is.
   > GitHub pauses scheduled workflows in repositories with no commits for 60 days. If that happens, re-enable the workflow in the Actions tab.

## 2. ESP32

### Wiring

| OLED | ESP32 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 21 |
| SCL | GPIO 22 |

### Upload (Arduino IDE 2.x)

1. In **Boards Manager**, install "esp32 by Espressif Systems" (version 3.x).
2. In **Library Manager**, install "Adafruit SSD1306". If it asks about Adafruit GFX and BusIO, choose *Install all*.
3. Open `firmware/ESP_Buddy/ESP_Buddy.ino`. The other files in the folder (`config.h`, `font_text.h`, `font_clock.h`) open as tabs automatically.
4. Select **Tools → Board → ESP32 Dev Module** and choose your port.
   - If the build fails with "Sketch too big", pick **Tools → Partition Scheme → "Huge APP (3MB No OTA/1MB SPIFFS)"**. That leaves 1 MB for screens, which is plenty, since one full set is about 130 KB.
5. Click **Upload**. If it cannot connect, hold the board's **BOOT** button while it uploads.
6. Open the **Serial Monitor** at 115200 baud with the line ending set to *Newline*.

### Testing without the phone

1. After boot you should see "ESP_Buddy v0.2", then "No content yet" with a bouncing ball. That means the display wiring works.
2. In the Serial Monitor, type `TIME 1793000000`, then `DEMO`. The device creates a clock screen and 3 demo screens and starts cycling through them. The bottom line of the clock shows Turkish letters, so you can check that they render.
3. Other commands to try: `INFO`, `LIST`, `NEXT`, `PAUSE`, `RESUME`, `BRIGHTNESS 40`, `CLEAR`.

## 3. iPhone

Safari and Chrome on iPhone cannot use Bluetooth, so you need a browser with Web Bluetooth.

1. Install **Bluefy – Web BLE Browser** from the App Store.
2. In Bluefy, open **https://ekagansahin.github.io/ESP_Buddy/** and bookmark it.
3. Choose the language with **EN / TR** at the top. Both the page and the screens sent to the device switch.
4. Tap **Connect & send** and pick **ESP_Buddy** from the list. The page then:
   - syncs the time,
   - clears the device,
   - sends the selected screens (with a progress bar; a corrupted file is retried up to 3 times),
   - starts playback.
5. While connected you can use the remote: ◀ ❚❚ ▶, time sync and brightness.
6. To skip a screen, untick its card. The phone remembers your selection.

**Everyday use:** open the page and tap **Connect & send**. The device keeps the last screens even through a power cut. Only the time is lost, and it is synced again the next time you connect.

You can also send from a computer: open the same address in Chrome or Edge on a computer with Bluetooth.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Blank display, "OLED not found" in the Serial Monitor | Check that SDA and SCL are not swapped. If it still fails, set `OLED_ADDRESS` to `0x3D` in `config.h` |
| A 2-pixel shift or garbage on the right edge | The module may be an SH1106; the driver needs changing |
| The iPhone device list is empty | Make sure the device is powered. Check Bluefy's Bluetooth permission (Settings → Bluefy). Disconnect any other phone that is connected to it |
| "This browser has no Web Bluetooth" | Open the page in Bluefy, not Safari or Chrome |
| `ERR DONE crc` during a transfer | The page retries by itself. If it happens often, move the phone closer |
| Some screens are missing | Check the Actions summary for APIs marked ⚠️. They usually recover on the next run |
| Old data | Run the workflow by hand: Actions → Run workflow |
| No clock screen | The time has not been synced yet. Connect from the page; it syncs automatically |
