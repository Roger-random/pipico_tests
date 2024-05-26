import time
import board
import microcontroller

import asyncio
import neopixel

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

async def main():
    led_task = asyncio.create_task(blink_rgb(board.NEOPIXEL, 25, 0.05, 0.1, 1.0))
    await asyncio.gather(led_task)

asyncio.run(main())
