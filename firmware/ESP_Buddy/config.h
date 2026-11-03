#pragma once
// ESP_Buddy — hardware and protocol settings

#define FW_VERSION      "0.2"

// --- OLED (SSD1306, I2C, 128x64 monochrome) ---
#define OLED_SDA        21
#define OLED_SCL        22
#define OLED_ADDRESS    0x3C      // some modules use 0x3D
#define SCREEN_W        128
#define SCREEN_H        64

// --- Brightness ---
#define DAY_CONTRAST    0xCF      // changed with the BRIGHTNESS command
#define NIGHT_CONTRAST  1
#define NIGHT_START     0         // local hour — dimmed from this hour...
#define NIGHT_END       7         // ...until this hour (only once the time is known)

// --- BLE ---
#define BLE_NAME        "ESP_Buddy"
#define SERVICE_UUID    "68961d5e-4b75-4893-bb3e-14ce93b54693"
#define COMMAND_UUID    "0c3fb439-03a5-4085-ad4e-c2975815cf1a"  // phone -> ESP (write), text commands
#define DATA_UUID       "c34519c8-f6e2-4dba-9be7-f5591b429020"  // phone -> ESP (write / write without response), raw bytes
#define STATUS_UUID     "ae53dc3e-1ba9-4f77-b87c-428aa72328e8"  // ESP -> phone (notify), text replies

// --- Content ---
#define SCREEN_DIR          "/s"      // LittleFS folder holding the screen files
#define MAX_FILE            48000     // max bytes per file (buffered in RAM; same as generator/generate.py)
#define DEFAULT_DURATION_S  6         // used when a file header says 0
#define PROGRESS_STEP       1024      // PROGRESS every this many bytes (+ once when complete); the page uses it as flow control
#define DEFAULT_OFFSET_MIN  180       // TIME command default UTC offset (Turkey, UTC+3)
#define RECEIVE_TIMEOUT_MS  30000     // leave receive mode after this long without activity
