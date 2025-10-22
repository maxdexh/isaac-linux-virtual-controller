from collections.abc import Callable, Iterable
import functools
from typing import Literal

import uinput  # type: ignore
import evdev  # type: ignore
from evdev import KeyEvent, ecodes

type InKey = int
type OutEvent = tuple[int, int]
type OutEventValue = int

# Values for pressed and released.
# Also used for the analog shoulder triggers
BTN_DOWN_VAL: OutEventValue = 1
BTN_UP_VAL: OutEventValue = 0

# Thumbpad values along one axis. neutral is no
# deflection, the others are full deflection,
# with direction depending on event
THUMB_MAX_VAL: OutEventValue = 255
THUMB_MIN_VAL: OutEventValue = 0
THUMB_NEUTRAL_VAL: OutEventValue = 128


type InKeyAction = Callable[[bool], None]
type InKeyListener = tuple[InKey, InKeyAction]


def build_keybinds(out_device: uinput.Device) -> Iterable[InKeyListener]:
    def emit(event: OutEvent, value: OutEventValue) -> None:
        print(f"{event=}, {value=}")
        out_device.emit(event, value)

    def direction_keys_to_axis(
        *,
        lo_on: InKey,
        hi_on: InKey,
        send: OutEvent,
    ) -> Iterable[InKeyListener]:
        lo_hi_state = [False, False]

        def on_change(idx: Literal[0, 1], value: bool) -> None:
            lo_hi_state[idx] = value
            lo, hi = lo_hi_state
            emit(
                send,
                THUMB_NEUTRAL_VAL
                if lo == hi
                else (THUMB_MIN_VAL if lo else THUMB_MAX_VAL),
            )

        return (
            (lo_on, functools.partial(on_change, 0)),
            (hi_on, functools.partial(on_change, 1)),
        )

    def key_to_button(*, on: InKey, send: OutEvent) -> InKeyListener:
        def handler(pressed: bool) -> None:
            emit(send, BTN_DOWN_VAL if pressed else BTN_UP_VAL)

        return (on, handler)

    return (
        # Movement keys
        *direction_keys_to_axis(
            lo_on=ecodes.KEY_A,
            hi_on=ecodes.KEY_D,
            send=uinput.ABS_X,
        ),
        *direction_keys_to_axis(
            lo_on=ecodes.KEY_W,
            hi_on=ecodes.KEY_S,
            send=uinput.ABS_Y,
        ),
        # Fire keys
        key_to_button(on=ecodes.KEY_DOWN, send=uinput.BTN_A),
        key_to_button(on=ecodes.KEY_RIGHT, send=uinput.BTN_B),
        key_to_button(on=ecodes.KEY_LEFT, send=uinput.BTN_X),
        key_to_button(on=ecodes.KEY_UP, send=uinput.BTN_Y),
        # Use keys
        key_to_button(on=ecodes.KEY_Q, send=uinput.BTN_TR),
        key_to_button(on=ecodes.KEY_E, send=uinput.BTN_TL),
        key_to_button(on=ecodes.KEY_SPACE, send=uinput.ABS_Z),
        # Other action keys
        key_to_button(on=ecodes.KEY_LEFTCTRL, send=uinput.ABS_RZ),
        # Used to join multiplayer and interact with the map
        key_to_button(on=ecodes.KEY_TAB, send=uinput.BTN_SELECT),
        # Hold together with thumbr to reset run
        key_to_button(on=ecodes.KEY_J, send=uinput.BTN_THUMBL),
        # Emote
        key_to_button(on=ecodes.KEY_K, send=uinput.BTN_THUMBR),
        # Join game (local multiplayer)
        key_to_button(on=ecodes.KEY_4, send=uinput.BTN_START),
    )


def create_device() -> uinput.Device:
    # uinput values for ABS events: (min, max, fuzz, flat).
    # shoulder triggers are treated as buttons.
    thumb_dat = (THUMB_MIN_VAL, THUMB_MAX_VAL, 0, 0)
    shoulder_dat = (BTN_UP_VAL, BTN_DOWN_VAL, 0, 0)

    return uinput.Device(
        # WARN: Changing what events are available also affects what those events do!
        # For example, removing ABS_RX and ABS_RY will cause ABS_Z and ABS_RZ to take
        # their place. Check the input test in the steam controller settings and reset
        # device inputs if weird things start happening.
        [
            # analog left thumbpad
            uinput.ABS_X + thumb_dat,  # left/right
            uinput.ABS_Y + thumb_dat,  # up/down
            uinput.BTN_THUMBR,  # thumbpad press
            # analog right thumbpad
            uinput.ABS_RX + thumb_dat,  # left/right
            uinput.ABS_RY + thumb_dat,  # up/down
            uinput.BTN_THUMBL,  # thumbpad press
            # (analog) shoulder triggers
            uinput.ABS_Z + shoulder_dat,  # left
            uinput.ABS_RZ + shoulder_dat,  # right
            # shoulder buttons
            uinput.BTN_TL,
            uinput.BTN_TR,
            # "middle" buttons
            uinput.BTN_START,
            uinput.BTN_SELECT,
            # ABXY
            uinput.BTN_A,
            uinput.BTN_B,
            uinput.BTN_X,
            uinput.BTN_Y,
        ],
        vendor=0x045E,
        product=0x028E,
        version=0x110,
        name="Microsoft X-Box 360 pad",
    )


def main() -> None:
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

    with create_device() as out_device:
        keymap: dict[InKey, list[InKeyAction]] = {}
        for on, action in build_keybinds(out_device):
            keymap.setdefault(on, []).append(action)

        if not devices:
            print("No input devices found. Run as root?")
            return

        print("Available devices:")
        for i, device in enumerate(devices):
            print(device.path, device.name, device.phys)

        while True:
            try:
                print()
                device_id = int(input("Pick device /dev/input/event[...]: "))
                device = next(
                    device
                    for device in devices
                    if device.path.endswith(f"event{device_id}")
                )
                break
            except Exception:
                pass

        for event in device.read_loop():
            if event.type != evdev.ecodes.EV_KEY:
                continue

            key_event = evdev.categorize(event)
            if key_event.keystate == KeyEvent.key_down:
                pressed = True
            elif key_event.keystate == KeyEvent.key_up:
                pressed = False
            else:
                continue

            for act in keymap.get(event.code, ()):
                act(pressed)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        import sys

        sys.exit(130)
