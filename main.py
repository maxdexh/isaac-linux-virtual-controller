import dataclasses
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import functools

import uinput  # type: ignore
import evdev  # type: ignore
from evdev import KeyEvent, ecodes


type InKey = int
type OutEvent = tuple[int, int]
type OutEventValue = int
type Keymap = Mapping[InKey, KeyAction]
type Keybind = tuple[InKey, KeyAction]

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


@dataclass(frozen=True)
class KeyAction:
    _: dataclasses.KW_ONLY
    on_press: Callable[[], None]
    on_release: Callable[[], None]

    @staticmethod
    def from_handler(handler: Callable[[bool], None]) -> "KeyAction":
        return KeyAction(
            on_press=functools.partial(handler, True),
            on_release=functools.partial(handler, False),
        )


@dataclass
class OutThumbpadAxis:
    """
    Tracks state of a bidirectional input along an axis.
    If both directions are pressed, they cancel each other until one is released.
    """

    event: OutEvent
    hi: bool = dataclasses.field(default=False, init=False)
    lo: bool = dataclasses.field(default=False, init=False)

    def update_device(self):
        OUT_DEVICE.emit(
            self.event,
            THUMB_NEUTRAL_VAL
            if self.lo == self.hi
            else (THUMB_MIN_VAL if self.lo else THUMB_MAX_VAL),
        )

    def send_lo(self, value: bool) -> None:
        self.lo = value
        self.update_device()

    def send_hi(self, value: bool) -> None:
        self.hi = value
        self.update_device()


class OutDevice:
    def __init__(self) -> None:
        # uinput values for ABS events: (min, max, fuzz, flat).
        # shoulder triggers are treated as buttons.
        thumb_dat = (THUMB_MIN_VAL, THUMB_MAX_VAL, 0, 0)
        shoulder_dat = (BTN_UP_VAL, BTN_DOWN_VAL, 0, 0)

        self.device = uinput.Device(
            # WARN: Changing what events are available also affects what those events do!
            # For example, removing ABS_RX and ABS_RY will cause ABS_Z and ABS_RZ to take
            # their place. Check the input test in the steam controller settings and reset
            # device inputs if weird things start happening.
            [
                # left thumbpad
                uinput.ABS_X + thumb_dat,  # left/right
                uinput.ABS_Y + thumb_dat,  # up/down
                uinput.BTN_THUMBR,  # thumbpad press
                # right thumbpad
                uinput.ABS_RX + thumb_dat,  # left/right
                uinput.ABS_RY + thumb_dat,  # up/down
                uinput.BTN_THUMBL,  # thumbpad press
                # analog shoulder triggers, treated as buttons
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

    def emit(self, event: OutEvent, value: OutEventValue) -> None:
        print(f"{event=}, {value=}")
        self.device.emit(event, value)


def get_keybinds() -> Iterable[Keybind]:
    def simple_button(event: OutEvent) -> KeyAction:
        def handler(pressed: bool) -> None:
            OUT_DEVICE.emit(event, BTN_DOWN_VAL if pressed else BTN_UP_VAL)

        return KeyAction.from_handler(handler)

    def direction_keys_to_axis(
        *,
        lo_on: InKey,
        hi_on: InKey,
        send: OutEvent,
    ) -> Iterable[Keybind]:
        axis = OutThumbpadAxis(send)
        return (
            (lo_on, KeyAction.from_handler(axis.send_lo)),
            (hi_on, KeyAction.from_handler(axis.send_hi)),
        )

    def key_to_button(*, on: InKey, send: OutEvent) -> Keybind:
        def handler(pressed: bool) -> None:
            OUT_DEVICE.emit(send, BTN_DOWN_VAL if pressed else BTN_UP_VAL)

        return (on, KeyAction.from_handler(handler))

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


OUT_DEVICE = OutDevice()


def main() -> None:
    keymap: dict[InKey, KeyAction] = {}
    for k, a in get_keybinds():
        if k in keymap:
            raise ValueError(f"Duplicate key {k}")
        keymap[k] = a

    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

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

        if (action := keymap.get(event.code)) is None:
            continue

        key_event = evdev.categorize(event)
        if key_event.keystate == KeyEvent.key_down:
            action.on_press()
        elif key_event.keystate == KeyEvent.key_up:
            action.on_release()
        else:
            continue


if __name__ == "__main__":
    main()
