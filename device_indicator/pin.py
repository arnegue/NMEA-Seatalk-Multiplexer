from abc import ABCMeta, abstractmethod
import logger
from threading import Lock
try:
    import smbus2
except ModuleNotFoundError:
    pass


class Pin(object, metaclass=ABCMeta):
    """
    Since there are LEDs to set with device indicator, there has to be some abstraction if they are conntected directoly to GPIO or SPI or I2C or what ever
    """
    def __init__(self, inverted_polarity):
        """
        Constructor, just sets the polarity

        :param inverted_polarity: if set to True the polarity will be inverted
        """
        self._inverted = inverted_polarity

    @abstractmethod
    def set_high(self):
        """
        Switches the indicator on
        :return:
        """
        raise NotImplementedError()

    @abstractmethod
    def set_low(self):
        """
        Switches the indicator off
        """
        raise NotImplementedError()


class I2CPin(Pin):
    class I2CMaskMutex(object):
        def __init__(self):
            self.mask = 0xFFFF
            self.lock = Lock()

    i2c_address_dict = {}  # Dictionary containing Mutex and current pin-mask

    def __init__(self, i2c_address, pin_nr, inverted_polarity):
        """
        Pin accessible via I2C

        :param i2c_address: I2Address of Device
        :param pin_nr: Number of pin connected in device
        :param inverted_polarity: if set to True the polarity will be inverted
        """
        super().__init__(inverted_polarity)
        self._pin_nr = pin_nr
        self.i2c_address = i2c_address

    def set_high(self):
        self._set(self.i2c_address, self._pin_nr, not self._inverted)

    def set_low(self):
        self._set(self.i2c_address, self._pin_nr, self._inverted)

    @classmethod
    def _set(cls, i2c_address, pin, high):
        if i2c_address not in cls.i2c_address_dict:
            cls.i2c_address_dict[i2c_address] = cls.I2CMaskMutex()

        mask_mutex = cls.i2c_address_dict[i2c_address]

        with mask_mutex.lock:
            if high:
                mask_mutex.mask |= 1 << pin
            else:
                mask_mutex.mask &= ~(1 << pin)

            cls._write_mask_to_bus(i2c_address, mask_mutex.mask)

    @staticmethod
    def _write_mask_to_bus(i2c_address, mask):
        buffer = [mask >> 8, mask & 0x00FF]
        try:
            with smbus2.SMBus(0) as bus:
                bus.write_i2c_block_data(i2c_address, 0, buffer)
        except OSError as oe:
            logger.error(f"Error writing {i2c_address} to I2C-Bus: {repr(oe)}")


class DebugPin(Pin):
    def set_high(self):
        pass

    def set_low(self):
        pass
