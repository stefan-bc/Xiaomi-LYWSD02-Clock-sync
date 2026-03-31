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

G = '\033[92m'; Y = '\033[93m'; C = '\033[96m'; R = '\033[91m'
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
    print(f'\n  {B}LYWSD02 Sync{X}  {D}{datetime.now().strftime("%H:%M")}{X}\n  {D}Scanning...{X}')
    clocks = await find_clocks()
    if not clocks:
        print(f'  {R}None found.{X}\n')
        return

    ok = fail = 0
    for d in clocks:
        t, h = await sync_clock(d)
        if t is False:
            fail += 1
            print(f'  {R}✗{X} {d.name}')
        elif t is not None:
            ok += 1
            print(f'  {G}✓{X} {d.name}  {Y}{t:.1f}°C{X}  {C}{h}%{X}')
        else:
            ok += 1
            print(f'  {G}✓{X} {d.name}')

    print(f'\n  {G}{ok}{X}/{ok+fail}', end='')
    if fail:
        print(f'  {R}({fail} failed){X}', end='')
    print('\n')


if __name__ == '__main__':
    if '--scan' in sys.argv:
        asyncio.run(scan(save='--save' in sys.argv))
    else:
        asyncio.run(sync_all())
