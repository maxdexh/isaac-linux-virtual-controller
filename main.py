from typing import Callable, Any
from dataclasses import dataclass

import uinput  # type: ignore
import evdev  # type: ignore
from evdev import KeyEvent, ecodes


type Keybind = Callable[[bool], None]
type Key = Any
type Event = tuple


def simple_button(event: Event) -> Keybind:
    def handler(release):
        emit(event, 0 if release else 1)

    return handler


# State of the left thumbpad, whether each direction is pressed
# (opposite directions can be pressed and cancel out until one is released)
@dataclass
class ThumbstickAxisState:
    """
    State of a bidirectional input along an axis.
    If both directions are pressed, they will cancel each other until one is released
    """

    event: Event
    hi: bool = False
    lo: bool = False

    def update_device(self):
        emit(self.event, 128 if self.lo == self.hi else (0 if self.lo else 255))

    def update_set_hi(self, release: bool):
        self.hi = not release
        self.update_device()

    def update_set_lo(self, release: bool):
        self.lo = not release
        self.update_device()


lpad_x = ThumbstickAxisState(uinput.ABS_X)  # left/right
lpad_y = ThumbstickAxisState(uinput.ABS_Y)  # up/down


# Maps keyboard keys to actions
keymap: dict[int, Callable[[bool], None]] = {
    # Movement keys
    ecodes.KEY_A: lpad_x.update_set_lo,
    ecodes.KEY_D: lpad_x.update_set_hi,
    ecodes.KEY_W: lpad_y.update_set_lo,
    ecodes.KEY_S: lpad_y.update_set_hi,
    # Fire keys
    ecodes.KEY_DOWN: simple_button(uinput.BTN_A),
    ecodes.KEY_RIGHT: simple_button(uinput.BTN_B),
    ecodes.KEY_LEFT: simple_button(uinput.BTN_X),
    ecodes.KEY_UP: simple_button(uinput.BTN_Y),
    # Use keys
    ecodes.KEY_Q: simple_button(uinput.BTN_TR),
    ecodes.KEY_E: simple_button(uinput.BTN_TL),
    ecodes.KEY_SPACE: simple_button(uinput.ABS_Z),
    # Other action keys
    ecodes.KEY_LEFTCTRL: simple_button(uinput.ABS_RZ),
    # Used to join multiplayer and interact with the map
    ecodes.KEY_TAB: simple_button(uinput.BTN_SELECT),
    # Hold together with thumbr to reset run
    ecodes.KEY_J: simple_button(uinput.BTN_THUMBL),
    # Emote
    ecodes.KEY_K: simple_button(uinput.BTN_THUMBR),
    # Join game (local multiplayer)
    ecodes.KEY_4: simple_button(uinput.BTN_START),
}

device = uinput.Device(
    # WARN: Changing what events are available also affects what those events do!
    # For example, removing ABS_RX and ABS_RY will cause ABS_Z and ABS_RZ to take
    # their place. Check the input test in the steam controller settings and reset
    # device inputs if weird things start happening.
    [
        # left thumbpad
        uinput.ABS_X + (0, 255, 0, 0),  # left/right
        uinput.ABS_Y + (0, 255, 0, 0),  # up/down
        uinput.BTN_THUMBR,  # thumbpad press
        # right thumbpad
        uinput.ABS_RX + (0, 255, 0, 0),  # left/right
        uinput.ABS_RY + (0, 255, 0, 0),  # up/down
        uinput.BTN_THUMBL,  # thumbpad press
        # analog triggers
        uinput.ABS_Z + (0, 1, 0, 0),  # left
        uinput.ABS_RZ + (0, 1, 0, 0),  # right
        # sholder buttons
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


def emit(*args, **kwargs):
    print(args, kwargs)
    device.emit(*args, **kwargs)


def main():
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

        key_event = evdev.categorize(event)

        if (action := keymap.get(event.code)) is None:
            continue

        if key_event.keystate == KeyEvent.key_down:
            release = False
        elif key_event.keystate == KeyEvent.key_up:
            release = True
        else:
            continue

        action(release)


if __name__ == "__main__":
    main()
