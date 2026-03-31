#!/usr/bin/env python3
"""
LYWSD02 Clock Sync — CLI tool
Syncs time and reads sensors from all Xiaomi LYWSD02 thermometer clocks in range.

Usage:
  pip3 install bleak
  python3 sync.py          Scan, sync time, read sensors
  python3 sync.py --scan   Just list nearby clocks
"""

import asyncio
import json
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print('\n  bleak not installed. Run: pip3 install bleak\n')
    sys.exit(1)

# BLE UUIDs
TIME_SERVICE  = 'ebe0ccb0-7a0a-4b0c-8a1a-6ff2997da3a6'
TIME_CHAR     = 'ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6'
TEMP_HUM_CHAR = 'ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6'

# Load device names/locations from devices.json if present
DEVICES_FILE = Path(__file__).parent / 'devices.json'
DEVICE_INFO = {}
if DEVICES_FILE.exists():
    try:
        data = json.loads(DEVICES_FILE.read_text())
        for d in data.get('devices', []):
            DEVICE_INFO[d.get('name', '')] = d
    except Exception:
        pass

# ── Colours ──────────────────────────────────────────────────────────

BOLD    = '\033[1m'
DIM     = '\033[2m'
GREEN   = '\033[92m'
YELLOW  = '\033[93m'
CYAN    = '\033[96m'
RED     = '\033[91m'
MAGENTA = '\033[95m'
RESET   = '\033[0m'


def banner():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tz = time.strftime('%Z')
    print()
    print(f'  {BOLD}LYWSD02 Clock Sync{RESET}')
    print(f'  {DIM}{now} {tz}{RESET}')
    print()


def build_time_payload():
    ts = int(time.time())
    offset = -time.timezone // 3600
    if time.daylight and time.localtime().tm_isdst:
        offset += 1
    return struct.pack('<Ib', ts, offset)


def find_device_info(name):
    """Match a BLE device name to devices.json entry."""
    for key, info in DEVICE_INFO.items():
        if key and key in (name or ''):
            return info
    return None


# ── Scan ─────────────────────────────────────────────────────────────

async def scan():
    banner()
    print(f'  {DIM}Scanning for 10 seconds...{RESET}')
    print()

    devices = await BleakScanner.discover(timeout=10.0)
    found = []
    for d in devices:
        if d.name and 'LYWSD02' in d.name:
            found.append(d)

    if not found:
        print(f'  {RED}No LYWSD02 devices found.{RESET}')
        print()
        return

    print(f'  {GREEN}Found {len(found)} device(s):{RESET}')
    print()
    print(f'  {DIM}{"Name":<16} {"Address":<40}{RESET}')
    print(f'  {DIM}{"─" * 16} {"─" * 40}{RESET}')
    for d in found:
        print(f'  {d.name:<16} {d.address:<40}')
    print()


# ── Sync ─────────────────────────────────────────────────────────────

async def sync_clock(device):
    """Connect, sync time, read temp/humidity. Returns result dict."""
    result = {
        'name': device.name or '?',
        'address': device.address,
        'status': 'failed',
        'temp': None,
        'humidity': None,
    }

    try:
        async with BleakClient(device.address, timeout=10.0) as client:
            # Sync time
            await client.write_gatt_char(TIME_CHAR, build_time_payload())
            result['status'] = 'synced'

            # Read sensor via notification
            reading = asyncio.get_event_loop().create_future()

            def on_notify(sender, data):
                if not reading.done():
                    temp = struct.unpack_from('<h', data, 0)[0] / 100
                    hum = data[2]
                    reading.set_result((temp, hum))

            await client.start_notify(TEMP_HUM_CHAR, on_notify)
            try:
                temp, hum = await asyncio.wait_for(reading, timeout=5.0)
                result['temp'] = temp
                result['humidity'] = hum
            except asyncio.TimeoutError:
                pass
            await client.stop_notify(TEMP_HUM_CHAR)

    except Exception as e:
        result['error'] = str(e)

    return result


async def sync_all():
    banner()
    print(f'  {DIM}Scanning for LYWSD02 devices...{RESET}')
    print()

    devices = await BleakScanner.discover(timeout=10.0)
    clocks = [d for d in devices if d.name and 'LYWSD02' in d.name]

    if not clocks:
        print(f'  {RED}No LYWSD02 devices found in range.{RESET}')
        print()
        return

    print(f'  {GREEN}Found {len(clocks)} clock(s). Syncing...{RESET}')
    print()

    results = []
    for i, device in enumerate(clocks):
        label = f'[{i + 1}/{len(clocks)}]'
        print(f'  {DIM}{label}{RESET} {device.name} {DIM}({device.address}){RESET}', end='', flush=True)
        result = await sync_clock(device)
        results.append(result)

        if result['status'] == 'synced':
            parts = [f'{GREEN}✓ synced{RESET}']
            if result['temp'] is not None:
                parts.append(f'{YELLOW}{result["temp"]:.1f} °C{RESET}')
                parts.append(f'{CYAN}{result["humidity"]} %{RESET}')
            print(f'  {" │ ".join(parts)}')
        else:
            err = result.get('error', 'unknown error')
            print(f'  {RED}✗ {err}{RESET}')

    # ── Summary ──────────────────────────────────────────────────────

    synced = [r for r in results if r['status'] == 'synced']
    failed = [r for r in results if r['status'] == 'failed']

    print()
    print(f'  {BOLD}Summary{RESET}')
    print(f'  {"─" * 56}')

    if synced:
        print()
        print(f'  {DIM}{"Device":<16} {"Temp":>8} {"Humidity":>10} {"Address"}{RESET}')
        print(f'  {DIM}{"─" * 16} {"─" * 8} {"─" * 10} {"─" * 20}{RESET}')
        for r in synced:
            temp_str = f'{r["temp"]:.1f} °C' if r['temp'] is not None else '—'
            hum_str = f'{r["humidity"]} %' if r['humidity'] is not None else '—'
            print(f'  {r["name"]:<16} {YELLOW}{temp_str:>8}{RESET} {CYAN}{hum_str:>10}{RESET} {DIM}{r["address"]}{RESET}')

    if failed:
        print()
        for r in failed:
            print(f'  {RED}✗ {r["name"]}{RESET} {DIM}{r.get("error", "")}{RESET}')

    print()
    print(f'  {GREEN}{len(synced)} synced{RESET}', end='')
    if failed:
        print(f'  {RED}{len(failed)} failed{RESET}', end='')
    print()
    print()


# ── Entry ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if '--scan' in sys.argv:
        asyncio.run(scan())
    else:
        asyncio.run(sync_all())
