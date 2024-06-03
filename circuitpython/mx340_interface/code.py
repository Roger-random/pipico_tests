import board
import asyncio
import digitalio
import busio

import adafruit_framebuf

# Copied MVLSBFormat from
# https://github.com/adafruit/Adafruit_CircuitPython_framebuf/blob/main/adafruit_framebuf.py
# Then modified from least-significant bit nearest top of screen to most-significant-bit up top
class MVMSBFormat:
    """MVMSBFormat"""

    @staticmethod
    def set_pixel(framebuf, x, y, color):
        """Set a given pixel to a color."""
        index = (y >> 3) * framebuf.stride + x
        offset = y & 0x07
        pixel_byte = 0x00
        if color != 0:
            pixel_byte = 0x80 >> offset
        framebuf.buf[index] = (framebuf.buf[index] & ~(0x80 >> offset)) | pixel_byte

    @staticmethod
    def get_pixel(framebuf, x, y):
        """Get the color of a given pixel"""
        index = (y >> 3) * framebuf.stride + x
        offset = y & 0x07
        return (framebuf.buf[index] << offset) & 0x80

    @staticmethod
    def fill(framebuf, color):
        """completely fill/clear the buffer with a color"""
        if color:
            fill = 0xFF
        else:
            fill = 0x00
        for i in range(len(framebuf.buf)):  # pylint: disable=consider-using-enumerate
            framebuf.buf[i] = fill

    @staticmethod
    def fill_rect(framebuf, x, y, width, height, color):
        """Draw a rectangle at the given location, size and color. The ``fill_rect`` method draws
        both the outline and interior."""
        # pylint: disable=too-many-arguments
        while height > 0:
            index = (y >> 3) * framebuf.stride + x
            offset = y & 0x07
            for w_w in range(width):
                pixel_byte = 0x00
                if color != 0:
                    pixel_byte = 0x80 >> offset
                framebuf.buf[index + w_w] = (
                    framebuf.buf[index + w_w] & ~(0x80 >> offset)
                ) | pixel_byte
            y += 1
            height -= 1

# Raw frame buffer byte array
framebuffer_bytearray = bytearray(196*5)

# FrameBuffer class for drawing on the byte array
framebuffer = adafruit_framebuf.FrameBuffer(
    framebuffer_bytearray, 196, 40, buf_format=adafruit_framebuf.MVLSB
)
framebuffer.format = MVMSBFormat()

# Frame buffer is made of 5 stripes. During data transmission each stripe is
# identified with the corresponding hexadecimal value
stripe_id_lookup = [b'\x04\x4D', b'\x04\xCD', b'\x04\x2D', b'\x04\xAD', b'\x04\x6D']

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

    await uart_sender(uart, rx_data, b'\x04\x74')
    await uart_sender(uart, rx_data, b'\x04\xF4')
    await uart_sender(uart, rx_data, b'\x04\x44')
    await uart_sender(uart, rx_data, b'\x04\x81')
    await uart_sender(uart, rx_data, b'\x04\x04')
    await uart_sender(uart, rx_data, b'\x04\x42') # This command moved frame buffer up by 2 pixels so 0x4D starts at 0,0

    print("Initialization sequence complete")

    await uart_sender(uart, rx_data, b'\x04\xF5') # Turn on LCD

    # Clear frame buffer
    framebuffer.fill(0)

    # Draw some stuff
    framebuffer.line(0, 0, 195, 33, 1)
    framebuffer.circle(20, 20, 10, 1)
    framebuffer.rect(120, 5, 50, 10, 1, fill=True)
    framebuffer.text("Hello FrameBuffer",5,5,1,font_name="lib/font5x8.bin")

    # Send to screen
    await send_lcd_frame(uart, rx_data)

async def send_lcd_frame(uart, rx_data):
    for stripe in range(5):
        await send_lcd_stripe(uart, rx_data, stripe)

async def send_lcd_stripe(uart, rx_data, stripe_num):
    stripe_slice_start = stripe_num*196
    stripe_slice_end = stripe_slice_start+196

    await uart_sender(uart, rx_data, stripe_id_lookup[stripe_num])
    await uart_sender(uart, rx_data, b'\x04\xC8')
    await uart_sender(uart, rx_data, b'\x04\x30')
    await uart_sender(uart, rx_data, b'\x06\xC4')

    await uart_sender(uart, rx_data, framebuffer_bytearray[stripe_slice_start:stripe_slice_end])

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
