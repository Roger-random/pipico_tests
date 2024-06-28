# For keyboard module salvaged from an Acer Aspire Switch 10

import board

from kmk.kmk_keyboard import KMKKeyboard
from kmk.keys import KC
from kmk.scanners import DiodeOrientation

keyboard = KMKKeyboard()

keyboard.col_pins = (board.GP12,board.GP13,board.GP14,board.GP15,board.GP16,board.GP17,board.GP18,board.GP19)
keyboard.row_pins = (board.GP1,board.GP2,board.GP3,board.GP4,board.GP5,board.GP6,board.GP7,board.GP8,board.GP9,board.GP10,board.GP11,board.GP20,board.GP21,board.GP22,board.A0,board.A1)
keyboard.diode_orientation = DiodeOrientation.ROW2COL

keyboard.keymap = [
    #12         13          14          15          16          17          18          19          Keyboard pins
    [KC.NO,     KC.UP,      KC.NO,      KC.NO,      KC.NO,      KC.DOWN,    KC.ESCAPE,  KC.NO,      # 1
     KC.BSPACE, KC.DELETE,  KC.RBRACKET,KC.QUOTE,   KC.NO,      KC.NO,      KC.NO,      KC.ENTER,   # 2
     KC.PGUP,   KC.NO,      KC.BSLASH,  KC.PGDOWN,  KC.NO,      KC.NO,      KC.NO,      KC.NO,      # 3
     KC.PSCREEN,KC.INSERT,  KC.EQUAL,   KC.LBRACKET,KC.NO,      KC.DOT,     KC.C,       KC.NO,      # 4
     KC.MINUS,  KC.PAUSE,   KC.NO,      KC.L,       KC.M,       KC.COMMA,   KC.SPACE,   KC.LEFT,    # 5
     KC.F12,    KC.F11,     KC.NO,      KC.N9,      KC.K,       KC.J,       KC.N,       KC.O,       # 6
     KC.F10,    KC.F9,      KC.N8,      KC.N7,      KC.I,       KC.H,       KC.B,       KC.U,       # 7
     KC.F8,     KC.F7,      KC.N6,      KC.T,       KC.G,       KC.V,       KC.NO,      KC.Y,       # 8
     KC.F6,     KC.F5,      KC.N5,      KC.E,       KC.D,       KC.F,       KC.NO,      KC.R,       # 9
     KC.F4,     KC.F3,      KC.N3,      KC.N4,      KC.S,       KC.RIGHT,   KC.NO,      KC.W,       # 10
     KC.F2,     KC.F1,      KC.N1,      KC.N2,      KC.A,       KC.Z,       KC.X,       KC.Q,       # 11
     KC.NO,     KC.NO,      KC.LSHIFT,  KC.SLASH,   KC.NO,      KC.RSHIFT,  KC.NO,      KC.NO,      # 20
     KC.NO,     KC.LCTRL,   KC.NO,      KC.N0,      KC.NO,      KC.NO,      KC.NO,      KC.NO,      # 21
     KC.LWIN,   KC.NO,      KC.NO,      KC.P,       KC.NO,      KC.NO,      KC.NO,      KC.NO,      # 22
     KC.NO,     KC.NO,      KC.NO,      KC.SCOLON,  KC.RALT,    KC.NO,      KC.LALT,    KC.NO,      # 23
     KC.GRAVE,  KC.NO,      KC.TAB,     KC.CAPSLOCK,KC.WINMENU, KC.NO,      KC.NO,      KC.NO,      # 24
     #                                       Special handling required for 19+24 = "Fn" ^^^^^
     ]
]

if __name__ == '__main__':
    keyboard.go()
