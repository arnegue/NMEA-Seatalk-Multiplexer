from enum import Enum, auto
from device_indicator.pin import Pin


class DeviceState(Enum):
    Initializing = auto()
    Reading = auto()
    Writing = auto()
    Active = auto()
    Error = auto()  # TimeOut, etc


class DeviceIndicator(object):
    def show_state(self, state: DeviceState):
        raise NotImplementedError()

    def reset_state(self):
        raise NotImplementedError


class LEDDeviceIndicator(DeviceIndicator):
    def __init__(self, pin: Pin):
        self._led_pin = pin

    def show_state(self, state: DeviceState):
        self._led_pin.set_high()

    def reset_state(self):
        self._led_pin.set_low()


class ThreePinLEDIndicator(DeviceIndicator):
    led_map = {
        DeviceState.Initializing: (True,  True,  True),   # White
        DeviceState.Reading:      (False, True,  True),   # Green
        DeviceState.Writing:      (False, False, True),   # Blue
        DeviceState.Active:       (True,  True,  False),  # Yellow
        DeviceState.Error:        (True,  False, False)   # Red
    }

    def __init__(self, led_red: LEDDeviceIndicator, led_green: LEDDeviceIndicator, led_blue: LEDDeviceIndicator):
        self._led_red = led_red
        self._led_green = led_green
        self._led_blue = led_blue

    def _show_rgb(self, r, g, b, state):
        self.set_led(self._led_red, r, state)
        self.set_led(self._led_green, g, state)
        self.set_led(self._led_blue, b, state)

    @staticmethod
    def set_led(led, show, state):
        led.show_state(state) if show else led.reset_state()

    def show_state(self, state: DeviceState):
        r, g, b = self.led_map[state]
        self._show_rgb(r, g, b, state)

    def reset_state(self):
        for led in self._led_red, self._led_green, self._led_blue:
            led.reset_state()
