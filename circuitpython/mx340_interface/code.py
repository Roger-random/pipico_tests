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
class K13988Display(adafruit_framebuf.FrameBuffer):
    def __init__(self, buffer_bytearray):
        super().__init__(buffer_bytearray, 196, 34)

        # Change format over to our custom format.
        self.format = MVMSBFormat()

framebuffer = K13988Display(framebuffer_bytearray)

class K13988:
    # Frame buffer is made of 5 stripes. During data transmission each stripe is
    # identified with the corresponding hexadecimal value
    stripe_id_lookup = [b'\x04\x4D', b'\x04\xCD', b'\x04\x2D', b'\x04\xAD', b'\x04\x6D']

    # Initialization sequence for NEC K13988 chip
    # Values came from logic analyzer watching behavior of a running MX340
    # This code sends the same bytes without understanding what they all mean
    k13988_init = [
        b'\xFE\xDC',
        b'\x0E\xFD', # Turn off "In Use/Memory" and "WiFi" LEDs
        b'\x0D\x3F',
        b'\x0C\xE1',
        b'\x07\xA1',
        b'\x03\x00',
        b'\x01\x00',
        b'\x0E\xFC', # Turn off "In Use/Memory" and "WiFi" LEDs... again?
        b'\x04\xD5',
        b'\x04\x85',
        b'\x04\x03',
        b'\x04\xC5',
        b'\x04\x34',
        # Logic analyzer reported that, after above sequence, the key matrix report
        # dropped from two bytes (0x80 0x40) to a single byte (0x80)
        b'\x04\x74',
        b'\x04\xF4',
        b'\x04\x44',
        b'\x04\x81',
        b'\x04\x04',
        b'\x04\x42', # This command moved frame buffer up by 2 pixels so 0x4D starts at 0,0
        b'\x04\xF5'  # Turn on LCD
    ]

    def __init__(self, tx_pin: microcontroller.Pin, rx_pin: microcontroller.Pin, enable_pin: microcontroller.Pin):
        self.transmit_startup = asyncio.Event()
        self.initialization_complete = asyncio.Event()
        self.last_report = 0x00
        self.ack_count = 0
        self.enable = digitalio.DigitalInOut(enable_pin)
        self.uart = busio.UART(tx_pin, rx_pin, baudrate=250000, bits=8, parity=busio.UART.Parity.EVEN, stop=2, timeout=20)
        self.transmit_lock = asyncio.Lock()

    # Data receive task
    async def uart_receiver(self):
        while True:
            while self.uart.in_waiting < 1:
                await asyncio.sleep(0)
            data = self.uart.read(1)[0]

            # First successful read complete, exit startup mode
            self.transmit_startup.set()

            if data == 0x20:
                self.ack_count += 1
            elif data == 0x40:
                # Ignore 0x40 as I have no idea what it means
                pass
            elif data != self.last_report:
                self.last_report = data
                print(f"New report 0x{data:X}")
            else:
                # Key matrix scan report unchanged, take no action
                pass

    # Wait for ACK
    async def wait_for_ack(self):
        while self.ack_count < 1:
            await asyncio.sleep(0)

    # Send data to K13988
    async def uart_sender(self, bytes):
        assert bytes is not None
        assert len(bytes) == 2 or len(bytes) == 196

        success = False

        while not success:
            sent = self.uart.write(bytes)
            assert sent == 2 or len(bytes) == 196

            try:
                await asyncio.wait_for(self.wait_for_ack(),0.02)
                self.ack_count -= 1
                success = True
            except asyncio.TimeoutError:
                print("Retrying 0x{0:X} 0x{1:X}".format(bytes[0],bytes[1]))

    # Initialize K13988
    async def initialize(self):
        print("Starting K13988 initialization")

        # Wait for first byte from K13988 before transmitting initialization
        await self.transmit_startup.wait()

        async with self.transmit_lock:
            for init_command in self.k13988_init:
                await self.uart_sender(init_command)

        print("Initialization sequence complete")
        self.initialization_complete.set()

        positions = [(50,4),(100,4),(100,16),(50,16)]

        while True:
            for pos in positions:
                framebuffer.fill(1)
                framebuffer.text("Bouncy",pos[0],pos[1],0,font_name="lib/font5x8.bin")
                await self.send_lcd_frame()
                await asyncio.sleep(0.2)

    async def send_lcd_frame(self):
        async with self.transmit_lock:
            for stripe in range(5):
                await self.send_lcd_stripe(stripe)

    async def send_lcd_stripe(self, stripe_num: int):
        stripe_slice_start = stripe_num*196
        stripe_slice_end = stripe_slice_start+196

        await self.uart_sender(self.stripe_id_lookup[stripe_num])
        await self.uart_sender(b'\x04\xC8')
        await self.uart_sender(b'\x04\x30')
        await self.uart_sender(b'\x06\xC4')

        await self.uart_sender(framebuffer_bytearray[stripe_slice_start:stripe_slice_end])

    # Blink "In Use/Memory" LED
    async def inuse_blinker(self):
        await self.initialization_complete.wait()

        while True:
            async with self.transmit_lock:
                await self.uart_sender(b'\x0E\xF9')
            await asyncio.sleep(0.1)
            async with self.transmit_lock:
                await self.uart_sender(b'\x0E\xFD')
            await asyncio.sleep(0.1)
            async with self.transmit_lock:
                await self.uart_sender(b'\x0E\xF9')
            await asyncio.sleep(0.1)
            async with self.transmit_lock:
                await self.uart_sender(b'\x0E\xFD')
            await asyncio.sleep(1)

    async def run(self):
        # Soft reset K13988 with disable + enable
        self.enable.switch_to_output(False)
        await asyncio.sleep(0.5)
        self.enable.value = True

        await asyncio.gather(
            self.uart_receiver(),
            self.inuse_blinker(),
            self.initialize())

async def main():
    k13988 = K13988(board.TX, board.RX, board.D2)
    await k13988.run()

asyncio.run(main())
