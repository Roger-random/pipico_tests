import time
import board
import microcontroller

import asyncio
import neopixel

import digitalio

import busio

# From https://learn.adafruit.com/adafruit-kb2040/circuitpython-pins-and-modules
board_pins = []
for pin in dir(microcontroller.pin):
    if isinstance(getattr(microcontroller.pin, pin), microcontroller.Pin):
        pins = []
        for alias in dir(board):
            if getattr(board, alias) is getattr(microcontroller.pin, pin):
                pins.append(f"board.{alias}")
        # Add the original GPIO name, in parentheses.
        if pins:
            # Only include pins that are in board.
            pins.append(f"({str(pin)})")
            board_pins.append(" ".join(pins))

for pins in sorted(board_pins):
    print(pins)

# asyncio smoke test with single NeoPixel LED
async def blink_rgb(pin, brightness_level, on_time, off_time, pause_time):
    with neopixel.NeoPixel(pin, 1) as px:
        while True:
            px.fill((brightness_level, 0, 0))
            await asyncio.sleep(on_time)
            px.fill((0, 0, 0))
            await asyncio.sleep(off_time)
            px.fill((0, brightness_level, 0))
            await asyncio.sleep(on_time)
            px.fill((0, 0, 0))
            await asyncio.sleep(off_time)
            px.fill((0, 0, brightness_level))
            await asyncio.sleep(on_time)
            px.fill((0, 0, 0))
            await asyncio.sleep(pause_time)

# A check to see if we're getting the data stream expected to be coming steadily from K13988 chip
async def startup_check(uart):
    while uart.in_waiting < 2:
        await asyncio.sleep(0)
    data = uart.read(2)
    assert data is not None
    if data == b'\x80\x40':
        print("Startup check: 0x80 0x40 as expected")
        return
    elif data == b'\x40\x80':
        print("Startup check: 0x40 0x80 might just be caused by tuning in at wrong time. Acceptable.")
        return
    elif data == b'\x80\x80':
        print("Startup check: 0x80 and it appears 0x40 has already been turned off. Acceptable.")
        return
    else:
        raise RuntimeError("Did not see byte sequence (0x80 0x40 or just 0x80) expected from K13988")

# UART communication with K13988 chip
async def k13988(tx, rx, enable):
    with digitalio.DigitalInOut(enable) as enable_pin, busio.UART(board.TX, board.RX, baudrate=250000, bits=8, parity=busio.UART.Parity.EVEN, stop=1, timeout=20) as uart:
        enable_pin.switch_to_output(True)
        await startup_check(uart)

async def main():
    led_task = asyncio.create_task(blink_rgb(board.NEOPIXEL, 25, 0.05, 0.1, 1.0))
    control_panel_task = asyncio.create_task(k13988(board.TX, board.RX, board.D2))
    await asyncio.gather(led_task, control_panel_task)

asyncio.run(main())
