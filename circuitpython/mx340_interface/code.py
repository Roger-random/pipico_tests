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

# Class that represents latest data heard from K13988
class ReceivedData:
    def __init__(self):
        self.last_report = 0x80
        self.report_unchanged_count = 0
        self.ack_count = 0
        self.ignored0x40_count = 0

# Data receive loop
async def uart_receiver(uart, rx_data):
    assert uart is not None
    assert rx_data is not None

    while True:
        while uart.in_waiting < 1:
            await asyncio.sleep(0)
        data = uart.read(1)[0]

        if data == 0x20:
            rx_data.ack_count += 1
        elif data == 0x40:
            rx_data.ignored0x40_count += 1
        elif data == rx_data.last_report:
            rx_data.report_unchanged_count += 1
        else:
            rx_data_print(rx_data)
            rx_data.last_report = data
            rx_data.report_unchanged_count = 0

# Print ReceivedData values to console
def rx_data_print(rx_data):
    print(f"0x{rx_data.last_report:x} for {rx_data.report_unchanged_count} / {rx_data.ack_count} ACK / {rx_data.ignored0x40_count} 0x40 ignored")
    rx_data.report_unchanged_count = 0
    rx_data.ack_count = 0
    rx_data.ignored0x40_count = 0

# Periodically dump ReceivedData values
async def rx_data_print_loop(rx_data):
    assert rx_data is not None

    while True:
        await asyncio.sleep(1.0)
        rx_data_print(rx_data)

# UART communication with K13988 chip
async def k13988(tx, rx, enable):
    rx_data = ReceivedData()

    with digitalio.DigitalInOut(enable) as enable_pin, busio.UART(board.TX, board.RX, baudrate=250000, bits=8, parity=busio.UART.Parity.EVEN, stop=1, timeout=20) as uart:
        enable_pin.switch_to_output(True)
        receiver = asyncio.create_task(uart_receiver(uart, rx_data))
        printer = asyncio.create_task(rx_data_print_loop(rx_data))
        await asyncio.gather(receiver, printer)

async def main():
    led_task = asyncio.create_task(blink_rgb(board.NEOPIXEL, 25, 0.05, 0.1, 1.0))
    control_panel_task = asyncio.create_task(k13988(board.TX, board.RX, board.D2))
    await asyncio.gather(led_task, control_panel_task)

asyncio.run(main())
