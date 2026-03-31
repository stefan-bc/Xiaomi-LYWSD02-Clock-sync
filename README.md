# LYWSD02 Clock Sync

Web and CLI tool to sync time and read temperature/humidity from Xiaomi LYWSD02 (LYWSD02MMC) BLE thermometer clocks.

## Web app

Open `index.html` in Chrome/Edge/Opera. Uses the Web Bluetooth API to connect to clocks, sync time, and read sensor data.

## CLI tool

Runs from terminal on macOS/Linux. Auto-discovers all LYWSD02 clocks in BLE range.

```
pip3 install bleak
curl -sL https://raw.githubusercontent.com/stefan-bc/LYWSD02-clock-sync/main/sync.py | python3
```

## BLE protocol

- **Time service:** `ebe0ccb0-7a0a-4b0c-8a1a-6ff2997da3a6`
- **Time characteristic:** `ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6` — 5 bytes: uint32 LE unix timestamp + int8 timezone offset hours
- **Temp/humidity characteristic:** `ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6` — notification: int16 LE temp (÷100 for °C) + uint8 humidity %

## Credits

Based on the [lywsd02](https://github.com/h4/lywsd02) Python client.

- [Harold De Armas](https://github.com/dearmash) — C/F unit support
- [Mitja Pugelj](https://www.linkedin.com/in/mitjapugelj)
