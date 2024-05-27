import time
import board
import microcontroller

import asyncio
import neopixel

import countio
import digitalio

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

# Use countio to watch for digital signal activity
async def count_drops(pin, sleep_period, label):
    with countio.Counter(pin) as watched:
        while True:
            await asyncio.sleep(sleep_period)
            print(label,watched.count)
            watched.count = 0

# Toggle digital output at regular intervals
async def digital_toggle(pin, on_time, off_time):
    with digitalio.DigitalInOut(pin) as togglee:
        togglee.switch_to_output(False)
        while True:
            await asyncio.sleep(off_time)
            togglee.value = True
            await asyncio.sleep(on_time)
            togglee.value = False

async def main():
    led_task = asyncio.create_task(blink_rgb(board.NEOPIXEL, 25, 0.05, 0.1, 1.0))
    count_d1 = asyncio.create_task(count_drops(board.D1, 1.0, "D1"))
    toggle_d2 = asyncio.create_task(digital_toggle(board.D2, 2.0, 3.0))
    await asyncio.gather(led_task, count_d1, toggle_d2)

asyncio.run(main())
