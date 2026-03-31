#!/usr/bin/env python3
"""
Sync time to all LYWSD02 clocks in range.
Uses bleak (cross-platform BLE). Works on macOS, Linux, Windows.

Usage:
  pip3 install bleak
  python3 sync.py

Add MAC addresses below. On macOS these are UUIDs, on Linux they're actual MACs.
To find them: python3 sync.py --scan
"""

import asyncio
import struct
import sys
import time
from datetime import datetime, timezone

from bleak import BleakClient, BleakScanner

# BLE UUIDs for the LYWSD02
TIME_SERVICE  = 'ebe0ccb0-7a0a-4b0c-8a1a-6ff2997da3a6'
TIME_CHAR     = 'ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6'
TEMP_HUM_CHAR = 'ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6'

# Add your clocks here. Use --scan to find addresses.
# On macOS: UUIDs like 'A1B2C3D4-E5F6-...'
# On Linux: MACs like 'A4:C1:38:XX:XX:XX'
CLOCKS = [
    # {'name': 'Clock 1', 'address': 'A4:C1:38:XX:XX:XX', 'location': 'Bedroom'},
]


def build_time_payload():
    """5 bytes: uint32 LE unix timestamp + int8 timezone offset in hours."""
    ts = int(time.time())
    offset = -time.timezone // 3600
    if time.daylight and time.localtime().tm_isdst:
        offset += 1
    return struct.pack('<Ib', ts, offset)


async def scan():
    """Scan for nearby LYWSD02 devices and print their addresses."""
    print('Scanning for 10 seconds...\n')
    devices = await BleakScanner.discover(timeout=10.0)
    found = False
    for d in devices:
        if d.name and 'LYWSD02' in d.name:
            print(f'  {d.name}  {d.address}')
            found = True
    if not found:
        print('  No LYWSD02 devices found.')
    print()


async def sync_clock(clock):
    """Connect to a clock, sync time, read temperature and humidity."""
    name = clock.get('name', clock['address'])
    print(f'  {name}: connecting...', end='', flush=True)

    try:
        async with BleakClient(clock['address'], timeout=10.0) as client:
            # Write time
            payload = build_time_payload()
            await client.write_gatt_char(TIME_CHAR, payload)
            print(' time synced', end='', flush=True)

            # Read temperature and humidity via notification
            reading = asyncio.get_event_loop().create_future()

            def on_notify(sender, data):
                if not reading.done():
                    temp = struct.unpack_from('<h', data, 0)[0] / 100
                    hum = data[2]
                    reading.set_result((temp, hum))

            await client.start_notify(TEMP_HUM_CHAR, on_notify)
            try:
                temp, hum = await asyncio.wait_for(reading, timeout=5.0)
                print(f' | {temp:.1f} °C | {hum} %')
            except asyncio.TimeoutError:
                print(' | (no sensor data)')
            await client.stop_notify(TEMP_HUM_CHAR)

    except Exception as e:
        print(f' FAILED: {e}')


async def sync_all():
    """Sync all configured clocks, or scan for any LYWSD02 in range."""
    clocks = CLOCKS

    # If no clocks configured, auto-discover
    if not clocks:
        print('No clocks configured. Scanning for LYWSD02 devices...\n')
        devices = await BleakScanner.discover(timeout=10.0)
        for d in devices:
            if d.name and 'LYWSD02' in d.name:
                clocks.append({'name': d.name, 'address': d.address})
        if not clocks:
            print('No LYWSD02 devices found in range.')
            return

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'Syncing {len(clocks)} clock(s) at {now}\n')

    for clock in clocks:
        await sync_clock(clock)

    print('\nDone.')


if __name__ == '__main__':
    if '--scan' in sys.argv:
        asyncio.run(scan())
    else:
        asyncio.run(sync_all())
