#!/usr/bin/env python3
"""
LYWSD02 Clock Sync

  pip3 install bleak
  python3 sync.py
  python3 sync.py --scan
  python3 sync.py --scan --save
"""

import asyncio, json, struct, sys, time
from datetime import datetime
from pathlib import Path

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print('\n  pip3 install bleak\n')
    sys.exit(1)

TIME_SERVICE  = 'ebe0ccb0-7a0a-4b0c-8a1a-6ff2997da3a6'
TIME_CHAR     = 'ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6'
TEMP_HUM_CHAR = 'ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6'
DEVICES_FILE  = Path(__file__).parent / 'devices.json'

# DaisyUI dark theme colours (approximate ANSI)
G = '\033[38;2;54;211;153m'   # success green
Y = '\033[38;2;251;189;35m'   # warning amber
C = '\033[38;2;81;182;255m'   # accent blue
R = '\033[38;2;255;111;97m'   # error red
D = '\033[2m'; B = '\033[1m'; X = '\033[0m'


def time_payload():
    ts = int(time.time())
    off = -time.timezone // 3600
    if time.daylight and time.localtime().tm_isdst:
        off += 1
    return struct.pack('<Ib', ts, off)


async def find_clocks():
    devices = await BleakScanner.discover(timeout=10.0)
    return [d for d in devices if d.name and 'LYWSD02' in d.name]


async def sync_clock(d):
    try:
        async with BleakClient(d.address, timeout=10.0) as c:
            await c.write_gatt_char(TIME_CHAR, time_payload())
            fut = asyncio.get_event_loop().create_future()
            def cb(_, data):
                if not fut.done():
                    fut.set_result((struct.unpack_from('<h', data, 0)[0] / 100, data[2]))
            await c.start_notify(TEMP_HUM_CHAR, cb)
            try:
                t, h = await asyncio.wait_for(fut, timeout=5.0)
                return t, h
            except asyncio.TimeoutError:
                return None, None
            finally:
                await c.stop_notify(TEMP_HUM_CHAR)
    except Exception:
        return False, False


async def scan(save=False):
    print(f'\n  {D}Scanning...{X}')
    clocks = await find_clocks()
    if not clocks:
        print(f'  {R}None found.{X}\n')
        return
    for i, d in enumerate(clocks):
        print(f'  {i+1}. {d.name}  {D}{d.address}{X}')
    print()
    if save:
        existing = {}
        if DEVICES_FILE.exists():
            try:
                for dev in json.loads(DEVICES_FILE.read_text()).get('devices', []):
                    existing[dev.get('address', dev.get('id', ''))] = dev
            except Exception:
                pass
        for d in clocks:
            if d.address not in existing:
                existing[d.address] = {'name': f'Clock {len(existing)+1}', 'address': d.address, 'ble_name': d.name, 'location': ''}
        DEVICES_FILE.write_text(json.dumps({'devices': list(existing.values())}, indent=2) + '\n')
        print(f'  {G}Saved to {DEVICES_FILE.name}{X}\n')


async def sync_all():
    tz = time.strftime('%Z')
    now = datetime.now().strftime('%H:%M')
    print(f'\n  {B}LYWSD02 Clock Sync{X}')
    print(f'  {D}Syncs time and reads temp/humidity from all Xiaomi clocks in BLE range.{X}')
    print(f'  {D}Timezone: {tz} | Time: {now}{X}')
    print(f'\n  {D}Scanning for devices (10s)...{X}\n')
    clocks = await find_clocks()
    if not clocks:
        print(f'  {R}No LYWSD02 clocks found. Make sure Bluetooth is on and clocks are nearby.{X}\n')
        return

    print(f'  Found {B}{len(clocks)}{X} clock(s). Syncing time and reading sensors...\n')

    ok = fail = 0
    for d in clocks:
        t, h = await sync_clock(d)
        if t is False:
            fail += 1
            print(f'  {R}✗{X} {d.name}  {D}could not connect{X}')
        elif t is not None:
            ok += 1
            print(f'  {G}✓{X} {d.name}  {Y}{t:.1f}°C{X}  {C}{h}%{X}')
        else:
            ok += 1
            print(f'  {G}✓{X} {d.name}  {D}synced{X}')

    print(f'\n  {B}Result:{X} {G}{ok} synced{X}', end='')
    if fail:
        print(f', {R}{fail} failed{X}', end='')
    print(f' out of {ok+fail} found')
    if fail:
        print(f'  {D}Tip: failed clocks were too far away or busy. Run again to retry.{X}')
    print()


if __name__ == '__main__':
    if '--scan' in sys.argv:
        asyncio.run(scan(save='--save' in sys.argv))
    else:
        asyncio.run(sync_all())
