import ctypes
import serial
from serial import Serial, win32, SerialException


class ParityException(SerialException):
    pass


class ParitySerial(Serial):
    pass


class WinParitySerial(ParitySerial):
    """
    This is nearly the same as the Windows implementation. The only difference is setting the (f)ErrorChar in _reconfigure_port
    """
    def __init__(self, *args, **kwargs):
        self.parity_replace_char = 0xFE
        self.parity_replace_byte = bytes([self.parity_replace_char])
        super().__init__(*args, **kwargs)
        
    def _reconfigure_port(self):
        """Set communication parameters on opened port."""
        if not self._port_handle:
            raise SerialException("Can only operate on a valid port handle")

        # Set Windows timeout values
        # timeouts is a tuple with the following items:
        # (ReadIntervalTimeout,ReadTotalTimeoutMultiplier,
        #  ReadTotalTimeoutConstant,WriteTotalTimeoutMultiplier,
        #  WriteTotalTimeoutConstant)
        timeouts = win32.COMMTIMEOUTS()
        if self._timeout is None:
            pass  # default of all zeros is OK
        elif self._timeout == 0:
            timeouts.ReadIntervalTimeout = win32.MAXDWORD
        else:
            timeouts.ReadTotalTimeoutConstant = max(int(self._timeout * 1000), 1)
        if self._timeout != 0 and self._inter_byte_timeout is not None:
            timeouts.ReadIntervalTimeout = max(int(self._inter_byte_timeout * 1000), 1)

        if self._write_timeout is None:
            pass
        elif self._write_timeout == 0:
            timeouts.WriteTotalTimeoutConstant = win32.MAXDWORD
        else:
            timeouts.WriteTotalTimeoutConstant = max(int(self._write_timeout * 1000), 1)
        win32.SetCommTimeouts(self._port_handle, ctypes.byref(timeouts))

        win32.SetCommMask(self._port_handle, win32.EV_ERR)

        # Setup the connection info.
        # Get state and modify it:
        comDCB = win32.DCB()
        win32.GetCommState(self._port_handle, ctypes.byref(comDCB))
        comDCB.BaudRate = self._baudrate

        if self._bytesize == serial.FIVEBITS:
            comDCB.ByteSize = 5
        elif self._bytesize == serial.SIXBITS:
            comDCB.ByteSize = 6
        elif self._bytesize == serial.SEVENBITS:
            comDCB.ByteSize = 7
        elif self._bytesize == serial.EIGHTBITS:
            comDCB.ByteSize = 8
        else:
            raise ValueError("Unsupported number of data bits: {!r}".format(self._bytesize))

        if self._parity == serial.PARITY_NONE:
            comDCB.Parity = win32.NOPARITY
            comDCB.fParity = 0  # Disable Parity Check
        elif self._parity == serial.PARITY_EVEN:
            comDCB.Parity = win32.EVENPARITY
            comDCB.fParity = 1  # Enable Parity Check
        elif self._parity == serial.PARITY_ODD:
            comDCB.Parity = win32.ODDPARITY
            comDCB.fParity = 1  # Enable Parity Check
        elif self._parity == serial.PARITY_MARK:
            comDCB.Parity = win32.MARKPARITY
            comDCB.fParity = 1  # Enable Parity Check
        elif self._parity == serial.PARITY_SPACE:
            comDCB.Parity = win32.SPACEPARITY
            comDCB.fParity = 1  # Enable Parity Check
        else:
            raise ValueError("Unsupported parity mode: {!r}".format(self._parity))

        if self._stopbits == serial.STOPBITS_ONE:
            comDCB.StopBits = win32.ONESTOPBIT
        elif self._stopbits == serial.STOPBITS_ONE_POINT_FIVE:
            comDCB.StopBits = win32.ONE5STOPBITS
        elif self._stopbits == serial.STOPBITS_TWO:
            comDCB.StopBits = win32.TWOSTOPBITS
        else:
            raise ValueError("Unsupported number of stop bits: {!r}".format(self._stopbits))

        comDCB.fBinary = 1  # Enable Binary Transmission
        # Char. w/ Parity-Err are replaced with 0xff (if fErrorChar is set to TRUE)
        if self._rs485_mode is None:
            if self._rtscts:
                comDCB.fRtsControl = win32.RTS_CONTROL_HANDSHAKE
            else:
                comDCB.fRtsControl = win32.RTS_CONTROL_ENABLE if self._rts_state else win32.RTS_CONTROL_DISABLE
            comDCB.fOutxCtsFlow = self._rtscts
        else:
            # checks for unsupported settings
            # XXX verify if platform really does not have a setting for those
            if not self._rs485_mode.rts_level_for_tx:
                raise ValueError(
                    'Unsupported value for RS485Settings.rts_level_for_tx: {!r}'.format(
                        self._rs485_mode.rts_level_for_tx,))
            if self._rs485_mode.rts_level_for_rx:
                raise ValueError(
                    'Unsupported value for RS485Settings.rts_level_for_rx: {!r}'.format(
                        self._rs485_mode.rts_level_for_rx,))
            if self._rs485_mode.delay_before_tx is not None:
                raise ValueError(
                    'Unsupported value for RS485Settings.delay_before_tx: {!r}'.format(
                        self._rs485_mode.delay_before_tx,))
            if self._rs485_mode.delay_before_rx is not None:
                raise ValueError(
                    'Unsupported value for RS485Settings.delay_before_rx: {!r}'.format(
                        self._rs485_mode.delay_before_rx,))
            if self._rs485_mode.loopback:
                raise ValueError(
                    'Unsupported value for RS485Settings.loopback: {!r}'.format(
                        self._rs485_mode.loopback,))
            comDCB.fRtsControl = win32.RTS_CONTROL_TOGGLE
            comDCB.fOutxCtsFlow = 0

        if self._dsrdtr:
            comDCB.fDtrControl = win32.DTR_CONTROL_HANDSHAKE
        else:
            comDCB.fDtrControl = win32.DTR_CONTROL_ENABLE if self._dtr_state else win32.DTR_CONTROL_DISABLE
        comDCB.fOutxDsrFlow = self._dsrdtr
        comDCB.fOutX = self._xonxoff
        comDCB.fInX = self._xonxoff
        comDCB.fNull = 0

        # DIFFERENCE TO pyserial's implementation
        comDCB.fErrorChar = 1  # Enable error char
        comDCB.ErrorChar = self.parity_replace_char

        comDCB.fAbortOnError = 0
        comDCB.XonChar = serial.XON
        comDCB.XoffChar = serial.XOFF

        if not win32.SetCommState(self._port_handle, ctypes.byref(comDCB)):
            raise SerialException(
                'Cannot configure port, something went wrong. '
                'Original message: {!r}'.format(ctypes.WinError()))

    def read(self, *args, **kwargs):
        read_byte = super().read(*args, **kwargs)
        if read_byte == self.parity_replace_byte:
            raise ParityException()
        return read_byte
