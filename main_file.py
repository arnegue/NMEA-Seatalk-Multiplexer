import time
from device_indicator import pin, led_device_indicator

TCP_PIN_R = 14
TCP_PIN_G = 7
TCP_PIN_B = 6


def main():
    pin.I2CPin.write_mask_to_bus()
    tcp = led_device_indicator.ThreePinLEDIndicator(led_red=led_device_indicator.LEDDeviceIndicator(pin.I2CPin(0x20, TCP_PIN_R, True)),
                                                    led_blue=led_device_indicator.LEDDeviceIndicator(pin.I2CPin(0x20, TCP_PIN_G, True)),
                                                    led_green=led_device_indicator.LEDDeviceIndicator(pin.I2CPin(0x20, TCP_PIN_B, True)))

    while 1:
        for state in led_device_indicator.DeviceState:
            tcp.show_state(state)
            time.sleep(0.5)



if __name__ == "__main__":
    main()
