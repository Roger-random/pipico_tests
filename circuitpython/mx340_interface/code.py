import board
import asyncio
import digitalio
import busio

import adafruit_framebuf

# Raw frame buffer byte array
framebuffer_bytearray = bytearray(196*5)

# FrameBuffer class for drawing on the byte array
framebuffer = adafruit_framebuf.FrameBuffer(
    framebuffer_bytearray, 196, 40, buf_format=adafruit_framebuf.MVLSB
)

# MicroPython framebuf defines a monochrome bitmap format VLSB: vertical bits, least significant bit on top.
# Adafruit's adafruit_framebuf supports the same format as MVLSB.
# Our LCD is very close, except we have most significant bit on top. So we have to reverse the bits
# in the frame buffer for transmission.

# Modified from https://stackoverflow.com/questions/746171/efficient-algorithm-for-bit-reversal-from-msb-lsb-to-lsb-msb-in-c

bit_reverse_lookup = bytes([
  0x00, 0x80, 0x40, 0xC0, 0x20, 0xA0, 0x60, 0xE0, 0x10, 0x90, 0x50, 0xD0, 0x30, 0xB0, 0x70, 0xF0,
  0x08, 0x88, 0x48, 0xC8, 0x28, 0xA8, 0x68, 0xE8, 0x18, 0x98, 0x58, 0xD8, 0x38, 0xB8, 0x78, 0xF8,
  0x04, 0x84, 0x44, 0xC4, 0x24, 0xA4, 0x64, 0xE4, 0x14, 0x94, 0x54, 0xD4, 0x34, 0xB4, 0x74, 0xF4,
  0x0C, 0x8C, 0x4C, 0xCC, 0x2C, 0xAC, 0x6C, 0xEC, 0x1C, 0x9C, 0x5C, 0xDC, 0x3C, 0xBC, 0x7C, 0xFC,
  0x02, 0x82, 0x42, 0xC2, 0x22, 0xA2, 0x62, 0xE2, 0x12, 0x92, 0x52, 0xD2, 0x32, 0xB2, 0x72, 0xF2,
  0x0A, 0x8A, 0x4A, 0xCA, 0x2A, 0xAA, 0x6A, 0xEA, 0x1A, 0x9A, 0x5A, 0xDA, 0x3A, 0xBA, 0x7A, 0xFA,
  0x06, 0x86, 0x46, 0xC6, 0x26, 0xA6, 0x66, 0xE6, 0x16, 0x96, 0x56, 0xD6, 0x36, 0xB6, 0x76, 0xF6,
  0x0E, 0x8E, 0x4E, 0xCE, 0x2E, 0xAE, 0x6E, 0xEE, 0x1E, 0x9E, 0x5E, 0xDE, 0x3E, 0xBE, 0x7E, 0xFE,
  0x01, 0x81, 0x41, 0xC1, 0x21, 0xA1, 0x61, 0xE1, 0x11, 0x91, 0x51, 0xD1, 0x31, 0xB1, 0x71, 0xF1,
  0x09, 0x89, 0x49, 0xC9, 0x29, 0xA9, 0x69, 0xE9, 0x19, 0x99, 0x59, 0xD9, 0x39, 0xB9, 0x79, 0xF9,
  0x05, 0x85, 0x45, 0xC5, 0x25, 0xA5, 0x65, 0xE5, 0x15, 0x95, 0x55, 0xD5, 0x35, 0xB5, 0x75, 0xF5,
  0x0D, 0x8D, 0x4D, 0xCD, 0x2D, 0xAD, 0x6D, 0xED, 0x1D, 0x9D, 0x5D, 0xDD, 0x3D, 0xBD, 0x7D, 0xFD,
  0x03, 0x83, 0x43, 0xC3, 0x23, 0xA3, 0x63, 0xE3, 0x13, 0x93, 0x53, 0xD3, 0x33, 0xB3, 0x73, 0xF3,
  0x0B, 0x8B, 0x4B, 0xCB, 0x2B, 0xAB, 0x6B, 0xEB, 0x1B, 0x9B, 0x5B, 0xDB, 0x3B, 0xBB, 0x7B, 0xFB,
  0x07, 0x87, 0x47, 0xC7, 0x27, 0xA7, 0x67, 0xE7, 0x17, 0x97, 0x57, 0xD7, 0x37, 0xB7, 0x77, 0xF7,
  0x0F, 0x8F, 0x4F, 0xCF, 0x2F, 0xAF, 0x6F, 0xEF, 0x1F, 0x9F, 0x5F, 0xDF, 0x3F, 0xBF, 0x7F, 0xFF
])

# Frame buffer is made of 5 stripes. During data transmission each stripe is
# identified with the corresponding hexadecimal value
stripe_id_lookup = bytes([0x4D, 0xCD, 0x2D, 0xAD, 0x6D])

# Buffer for reversing bits then transmitting a stripe
stripebuffer = bytearray(196)

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
            print(f"New report 0x{data:X}")
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
    assert len(bytes) == 2 or len(bytes) == 196
    assert rx_data is not None

    success = False

    while not success:
        sent = uart.write(bytes)
        assert sent == 2 or len(bytes) == 196

        try:
            await asyncio.wait_for(wait_for_ack(rx_data),0.02)
            rx_data.ack_count -= 1
            success = True
        except asyncio.TimeoutError:
            print("Retrying 0x{0:X} 0x{1:X}".format(bytes[0],bytes[1]))

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
    await uart_sender(uart, rx_data, b'\x0E\xFD') # Turn off "In Use/Memory" and "WiFi" LEDs
    await uart_sender(uart, rx_data, b'\x0D\x3F')
    await uart_sender(uart, rx_data, b'\x0C\xE1')
    await uart_sender(uart, rx_data, b'\x07\xA1')
    await uart_sender(uart, rx_data, b'\x03\x00')
    await uart_sender(uart, rx_data, b'\x01\x00')
    await uart_sender(uart, rx_data, b'\x0E\xFC') # Turn off "In Use/Memory" and "WiFi" LEDs... again?
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

    await uart_sender(uart, rx_data, b'\x04\x42') # This command moved frame buffer up by 2 pixels so 0x4D starts at 0,0

    await asyncio.sleep(0.1) # Mimicking MX340 behavior of a slight pause

    print("Initialization sequence complete")

    await uart_sender(uart, rx_data, b'\x04\xF5') # Turn on LCD

    # Clear frame buffer
    framebuffer.rect(0, 0, 195, 33, 0, fill=True)

    # Draw some stuff
    framebuffer.line(0, 0, 195, 33, 1)
    framebuffer.circle(20, 20, 10, 1)
    framebuffer.rect(120, 5, 50, 10, 1, fill=True)
    # RuntimeError: pystack exhausted
    #framebuffer.text("Hello FrameBuffer",5,5,1,font_name="lib/font5x8.bin")

    # Send to screen
    await send_lcd_frame(uart, rx_data)

async def send_lcd_frame(uart, rx_data):
    for stripe in range(5):
        await send_lcd_stripe(uart, rx_data, stripe)

async def send_lcd_stripe(uart, rx_data, stripe_num):
    id_command = bytearray(2)
    id_command[0] = 0x04
    id_command[1] = stripe_id_lookup[stripe_num]

    start = stripe_num*196

    for index in range(196):
        stripebuffer[index] = bit_reverse_lookup[framebuffer_bytearray[start+index]]

    await uart_sender(uart, rx_data, id_command)
    await uart_sender(uart, rx_data, b'\x04\xC8')
    await uart_sender(uart, rx_data, b'\x04\x30')
    await uart_sender(uart, rx_data, b'\x06\xC4')

    await uart_sender(uart, rx_data, stripebuffer)

# Blink "In Use/Memory" LED
async def inuse_blinker(uart, rx_data):
    while True:
        await uart_sender(uart, rx_data, b'\x0E\xF9')
        await asyncio.sleep(1)
        await uart_sender(uart, rx_data, b'\x0E\xFD')
        await asyncio.sleep(1)

# UART communication with K13988 chip
async def k13988(tx, rx, enable):
    rx_data = ReceivedData()

    with digitalio.DigitalInOut(enable) as enable_pin, busio.UART(board.TX, board.RX, baudrate=250000, bits=8, parity=busio.UART.Parity.EVEN, stop=2, timeout=20) as uart:
        # Soft reset K13988 with disable + enable
        enable_pin.switch_to_output(False)
        await asyncio.sleep(0.5)
        enable_pin.value = True

        await asyncio.gather(
            uart_receiver(uart, rx_data),
            initialize(uart, rx_data),
            inuse_blinker(uart, rx_data)
            )

async def main():
    await asyncio.gather(k13988(board.TX, board.RX, board.D2))

asyncio.run(main())
