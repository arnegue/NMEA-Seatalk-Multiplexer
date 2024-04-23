import os

if os.name == 'nt':
    from serial.serialwin32 import Serial, SerialException
    from serial import win32
    import ctypes

else:
    from serial.serialposix import Serial, SerialException
    import termios


from common.helper import get_numeric_byte_value


class ParityException(SerialException):
    pass


class WinParitySerial(Serial):
    """
    This is nearly the same as the Windows implementation. The only difference is setting the (f)ErrorChar in _reconfigure_port
    Raises ParityError on Read
    """
    PARITY_BYTES = [bytes([0xFE, ])]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def _reconfigure_port(self):
        super()._reconfigure_port()
        # Get state and modify it:
        comDCB = win32.DCB()
        win32.GetCommState(self._port_handle, ctypes.byref(comDCB))

        # DIFFERENCE TO pyserial's implementation
        comDCB.fErrorChar = 1  # Enable error char
        comDCB.ErrorChar = get_numeric_byte_value(self.PARITY_BYTES[0])

        if not win32.SetCommState(self._port_handle, ctypes.byref(comDCB)):
            raise SerialException(
                'Cannot configure port, something went wrong. '
                'Original message: {!r}'.format(ctypes.WinError()))

    def read(self, size=1):
        """
        Reads bytes, if parity_replace_char was received, raises ParityError
        """
        read_byte = super().read(size)
        if read_byte == self.PARITY_BYTES[0]:
            raise ParityException()
        return read_byte


class LinuxParitySerial(Serial):
    """
    Nearly the same as PosixSerial, but enables PARMRK and INPCK.
    Raises ParityError on Read
    """
    PARITY_BYTES = [bytes([0xFF, ]), bytes([0x00, ])]  # Bytes of a parity error (see termios' PARMRK)

    def _reconfigure_port(self, force_update=False):
        super()._reconfigure_port(force_update=force_update)

        try:
            orig_attr = termios.tcgetattr(self.fd)
            iflag, oflag, cflag, lflag, ispeed, ospeed, cc = orig_attr
        except termios.error as msg:      # if a port is nonexistent but has a /dev file, it'll fail here
            raise SerialException("Could not configure port: {}".format(msg))

        # DIFFERENCE TO pyserial's implementation
        iflag |= termios.PARMRK | termios.INPCK

        if force_update or [iflag, oflag, cflag, lflag, ispeed, ospeed, cc] != orig_attr:
            termios.tcsetattr(
                self.fd,
                termios.TCSANOW,
                [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])

    def read(self, size=1):
        """
        Reads bytes, if PARITY_BYTES were received, raises ParityError
        """
        if size != 1:
            raise AttributeError("Reading more than 1 byte not supported")
        if not hasattr(self, "last_byte"):
            self.last_byte = super().read(size)

        now_byte = super().read(size)
        if self.last_byte == self.PARITY_BYTES[0]:  # Might be parity error
            if now_byte == self.PARITY_BYTES[1]:
                self.last_byte = super().read(size)
                raise ParityException()
        return_byte = self.last_byte
        self.last_byte = now_byte
        return return_byte


if os.name == 'nt':
    ParitySerial = WinParitySerial
else:
    ParitySerial = LinuxParitySerial
