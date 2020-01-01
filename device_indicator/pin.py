import smbus2
import logger

class Pin(object):
    def __init__(self, inverted_polarity):
        self._inverted = inverted_polarity

    def set_high(self):
        raise NotImplementedError()

    def set_low(self):
        raise NotImplementedError()


class I2CPin(Pin):
    i2c_address = 0x00
    i2c_pin_mask = 0xFFFF

    def __init__(self, i2c_address, pin_nr, inverted_polarity):
        super().__init__(inverted_polarity)
        self._pin_nr = pin_nr
        self.__class__.i2c_address = i2c_address

    def set_high(self):
        self._set(self._pin_nr, not self._inverted)

    def set_low(self):
        self._set(self._pin_nr, self._inverted)

    @classmethod
    def _set(cls, pin, high):
        if high:
            cls.i2c_pin_mask |= 1 << pin
        else:
            cls.i2c_pin_mask &= ~(1 << pin)

        cls.write_mask_to_bus()

    @classmethod
    def write_mask_to_bus(cls):
        buffer = [cls.i2c_pin_mask >> 8, cls.i2c_pin_mask & 0x00FF]
        try:
            with smbus2.SMBus(0) as bus:
                bus.write_i2c_block_data(cls.i2c_address, 0, buffer)
        except OSError as oe:
            logger.error(f"Error writing {cls.i2c_pin_mask} to I2C-Bus: {repr(oe)}")


class DebugPin(Pin):
    def set_high(self):
        pass

    def set_low(self):
        pass
