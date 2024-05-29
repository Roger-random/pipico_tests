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
        self.last_report = 0x0
        self.ack_count = 0

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
            # Ignore 0x40 as I have no idea what it means
            pass
        elif data != rx_data.last_report:
            rx_data.last_report = data
            print(f"New report 0x{data:x}")
        else:
            # Key matrix scan report unchanged, take no action
            pass

# Wait for ACK
async def wait_for_ack(rx_data):
    while rx_data.ack_count < 1:
        await asyncio.sleep(0)

# Send data to K13988
async def uart_sender(uart, rx_data, bytes):
    assert uart is not None
    assert bytes is not None
    assert len(bytes) == 2
    assert rx_data is not None

    success = False

    while not success:
        sent = uart.write(bytes)
        assert sent == 2

        try:
            await asyncio.wait_for(wait_for_ack(rx_data),0.05)
            rx_data.ack_count -= 1
            success = True
        except:
            print("Timed out waiting for ACK, retrying")

# Initialize K13988
async def initialize(uart, rx_data):
    assert uart is not None
    assert rx_data is not None

    print("Starting K13988 initialization")

    # Mimicing MX340 behavior of a slight pause
    await asyncio.sleep(0.024)

    # Values came from logic analyzer watching behavior of a running MX340
    # This code sends the same bytes without understanding what they mean

    # Initial set of bytes sent in rapid succession.
    await uart_sender(uart, rx_data, b'\xFE\xDC')
    await uart_sender(uart, rx_data, b'\x0E\xFD')
    await uart_sender(uart, rx_data, b'\x0D\x3F')
    await uart_sender(uart, rx_data, b'\x0C\xE1')
    await uart_sender(uart, rx_data, b'\x07\xA1')
    await uart_sender(uart, rx_data, b'\x03\x00')
    await uart_sender(uart, rx_data, b'\x01\x00')
    await uart_sender(uart, rx_data, b'\x0E\xFC')
    await uart_sender(uart, rx_data, b'\x04\xD5')
    await uart_sender(uart, rx_data, b'\x04\x85')
    await uart_sender(uart, rx_data, b'\x04\x03')
    await uart_sender(uart, rx_data, b'\x04\xC5')
    await uart_sender(uart, rx_data, b'\x04\x34')

    # Logic analyzer reported that, after above sequence, the key matrix report
    # dropped from two bytes (0x80 0x40) to a single byte (0x80)

    await asyncio.sleep(0.017) # Mimicking MX340 behavior of a slight pause

    await uart_sender(uart, rx_data, b'\x04\x74')

    await asyncio.sleep(0.02) # Mimicking MX340 behavior of a slight pause

    await uart_sender(uart, rx_data, b'\x04\xF4')
    await uart_sender(uart, rx_data, b'\x04\x44')
    await uart_sender(uart, rx_data, b'\x04\x81')
    await uart_sender(uart, rx_data, b'\x04\x04')

    await asyncio.sleep(0.1) # Mimicking MX340 behavior of a slight pause

    print("Initialization sequence complete")

    await inuse_blinker(uart, rx_data)

# Blink "In Use/Memory" LED
async def inuse_blinker(uart, rx_data):
    while True:
        print("On")
        await uart_sender(uart, rx_data, b'\x0E\xF9')
        await asyncio.sleep(1)
        print("Off")
        await uart_sender(uart, rx_data, b'\x0E\xFD')
        await asyncio.sleep(1)

# UART communication with K13988 chip
async def k13988(tx, rx, enable):
    rx_data = ReceivedData()

    with digitalio.DigitalInOut(enable) as enable_pin, busio.UART(board.TX, board.RX, baudrate=250000, bits=8, parity=busio.UART.Parity.EVEN, stop=1, timeout=20) as uart:
        enable_pin.switch_to_output(True)
        receiver = asyncio.create_task(uart_receiver(uart, rx_data))
        initializer = asyncio.create_task(initialize(uart, rx_data))
        await asyncio.gather(receiver, initializer)

async def main():
    led_task = asyncio.create_task(blink_rgb(board.NEOPIXEL, 25, 0.05, 0.1, 1.0))
    control_panel_task = asyncio.create_task(k13988(board.TX, board.RX, board.D2))
    await asyncio.gather(led_task, control_panel_task)

asyncio.run(main())
