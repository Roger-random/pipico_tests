import time
import board
import neopixel
import microcontroller

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

pixels = neopixel.NeoPixel(board.NEOPIXEL, 1)

while True:
    pixels.fill((0, 0, 10))
    time.sleep(0.2)
    pixels.fill((0, 0, 0))
    time.sleep(0.1)
    pixels.fill((10, 0, 0))
    time.sleep(0.2)
    pixels.fill((0, 0, 0))
    time.sleep(0.1)
    pixels.fill((0, 10, 0))
    time.sleep(0.2)
    pixels.fill((0, 0, 0))
    time.sleep(0.5)
