import board
import asyncio
import digitalio
import busio

# Parent class of optional LCD screen FrameBuffer wrapper
import adafruit_framebuf

# Support keyboard event queue
from collections import deque
from keypad import Event

# Maximum length of keyboard event queue. Any additional events
# are discarded when the queue is full.
key_event_queue_length = 64

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

# FrameBuffer class for drawing on the byte array
class K13988_FrameBuffer(adafruit_framebuf.FrameBuffer):
    def __init__(self, buffer_bytearray):
        super().__init__(buffer_bytearray, 196, 34)

        # Change format over to our custom format.
        self.format = MVMSBFormat()

class K13988:
    def __init__(self, tx_pin: microcontroller.Pin, rx_pin: microcontroller.Pin, enable_pin: microcontroller.Pin):
        # Task synchronization
        self._transmit_lock = asyncio.Lock()
        self._transmit_startup = asyncio.Event()
        self._initialization_complete = asyncio.Event()

        # Hardware IO
        self._enable = digitalio.DigitalInOut(enable_pin)
        self._enable.switch_to_output(False)
        self._uart = busio.UART(tx_pin, rx_pin, baudrate=250000, bits=8, parity=busio.UART.Parity.EVEN, stop=2, timeout=20)

        # Raw frame buffer byte array
        self._framebuffer_bytearray = bytearray(196*5)

        # Internal state
        self._last_report = 0x80
        self._ack_count = 0
        self._led_state = bytearray(b'\x0E\xFD')
        self._key_event_queue = deque((), key_event_queue_length, True)

    # Get reference to raw frame buffer bytearray
    def get_frame_buffer_bytearray(self):
        return self._framebuffer_bytearray

    # Data receive task
    async def _uart_receiver(self):
        while True:
            while self._uart.in_waiting < 1:
                await asyncio.sleep(0)
            data = self._uart.read(1)[0]

            # First successful read complete, exit startup mode
            self._transmit_startup.set()

            if data == 0x20:
                self._ack_count += 1
            elif data == 0x40:
                # Ignore 0x40 as I have no idea what it means
                pass
            elif data != self._last_report:
                if (len(self._key_event_queue) < key_event_queue_length):
                    # Add event to queue reflecting change in key scan state
                    if self._last_report != 0x80:
                        self._key_event_queue.append(Event(self._last_report, False)) # Previous key released
                    if data != 0x80:
                        self._key_event_queue.append(Event(data, True)) # New key pressed
                else:
                    # No events are added if queue is full
                    pass
                self._last_report = data
            else:
                # Key matrix scan report unchanged, take no action
                pass

    # Wait for ACK
    async def _wait_for_ack(self):
        while self._ack_count < 1:
            await asyncio.sleep(0)

    # Send data to K13988
    async def _uart_sender(self, bytes):
        assert bytes is not None
        assert len(bytes) == 2 or len(bytes) == 196

        success = False

        while not success:
            sent = self._uart.write(bytes)
            assert sent == 2 or len(bytes) == 196

            try:
                await asyncio.wait_for(self._wait_for_ack(),0.02)
                self._ack_count -= 1
                success = True
            except asyncio.TimeoutError:
                print("Retrying 0x{0:X} 0x{1:X}".format(bytes[0],bytes[1]))

    # Initialization sequence for NEC K13988 chip
    # Values came from logic analyzer watching behavior of a running MX340
    # This code sends the same bytes without understanding what they all mean
    _k13988_init = [
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

    # Initialize K13988
    async def _initialize_k13988(self):
        # Wait for first byte from K13988 before transmitting initialization
        await self._transmit_startup.wait()

        async with self._transmit_lock:
            for init_command in self._k13988_init:
                await self._uart_sender(init_command)

        # Set initialization complete event
        self._initialization_complete.set()

    # Following precedence of RGBMatrix, method to send frame buffer to screen
    async def refresh(self):
        async with self._transmit_lock:
            for stripe in range(5):
                await self._send_lcd_stripe(stripe)

    # Frame buffer is made of 5 stripes. During data transmission each stripe is
    # identified with the corresponding hexadecimal value
    _stripe_id_lookup = [b'\x04\x4D', b'\x04\xCD', b'\x04\x2D', b'\x04\xAD', b'\x04\x6D']

    # Send to LCD one horizontal stripes of 8 vertical pixels.
    async def _send_lcd_stripe(self, stripe_num: int):
        stripe_slice_start = stripe_num*196
        stripe_slice_end = stripe_slice_start+196

        await self._uart_sender(self._stripe_id_lookup[stripe_num])
        await self._uart_sender(b'\x04\xC8')
        await self._uart_sender(b'\x04\x30')
        await self._uart_sender(b'\x06\xC4')

        await self._uart_sender(self._framebuffer_bytearray[stripe_slice_start:stripe_slice_end])

    # Transmit LED sate to K13988
    async def _send_led_state(self):
        async with self._transmit_lock:
            await self._uart_sender(self._led_state)

    # Update bit flag corresponding to In Use/Memory LED based on parameter
    async def in_use_led(self, newState):
        if newState:
            self._led_state[1] = self._led_state[1] & 0b11111011
        else:
            self._led_state[1] = self._led_state[1] | 0b00000100
        await self._send_led_state()

    # Update bit flag corresponding to WiFi LED based on parameter
    async def wifi_led(self, newState):
        if newState:
            self._led_state[1] = self._led_state[1] | 0b00000010
        else:
            self._led_state[1] = self._led_state[1] & 0b11111101
        await self._send_led_state()

    # Get a key event. (If no event, returns None)
    def get_key_event(self):
        if len(self._key_event_queue) == 0:
            return None
        else:
            return self._key_event_queue.popleft()

    # Asynchronous context manager entry to set up K13988 communications
    async def __aenter__(self):
        # Soft reset K13988 with disable + enable
        self._enable.value = False
        await asyncio.sleep(0.25)
        self._enable.value = True

        # Start listener for K13988 data
        self.receiver_task = asyncio.create_task(self._uart_receiver())

        # Send initialization sequence
        await self._initialize_k13988()

        # We are all set up and ready for application code
        return self

    # Asynchronous context manager exit to clean up K13988 communications
    async def __aexit__(self, exc_type, exc, tb):
        self._enable.value = False
        self.receiver_task.cancel()

# Blink "In Use/Memory" LED
async def inuse_blinker(k13988):
    print("Starting inuse_blinker()")
    while True:
        await k13988.in_use_led(True)
        await asyncio.sleep(0.1)
        await k13988.in_use_led(False)
        await asyncio.sleep(0.1)
        await k13988.in_use_led(True)
        await asyncio.sleep(0.1)
        await k13988.in_use_led(False)
        await asyncio.sleep(1)

# Test FrameBuffer support by drawing text in various locations
async def bouncy_text(k13988):
    print("Starting bouncy_text()")
    positions = [(50,4),(100,4),(100,16),(50,16)]
    framebuffer = K13988_FrameBuffer(k13988.get_frame_buffer_bytearray())

    while True:
        for pos in positions:
            framebuffer.fill(1)
            framebuffer.text("Bouncy",pos[0],pos[1],0,font_name="lib/font5x8.bin")
            await k13988.refresh()
            await asyncio.sleep(0.2)

# Print key events to serial console
async def printkeys(k13988):
    print("Starting printkeys()")
    while True:
        key = k13988.get_key_event()
        if key:
            if key.pressed:
                action = 'pressed'
            else:
                action = '        released'
            print("{2:8X} Key 0x{0:X} {1}".format(key.key_number, action, key.timestamp))
        await asyncio.sleep(0)

async def main():
    print("Starting main()")
    async with K13988(board.TX, board.RX, board.D2) as k13988:
        await asyncio.gather(inuse_blinker(k13988), bouncy_text(k13988), printkeys(k13988))

asyncio.run(main())
