import os
import serial

if os.name == 'nt':
    from serial.serialwin32 import Serial, SerialException
    from serial import win32
    import ctypes

else:
    from serial.serialposix import Serial, SerialException, CMSPAR
    import termios
    import fcntl


class ParityException(SerialException):
    pass


class WinParitySerial(Serial):
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


class LinuxParitySerial(Serial):
    """
    Nearly the same as PosixSerial, but enables PARMRK and INPCK
    """
    PARITY_BYTES = [bytes([0xFF, ]), bytes([0x00, ])]  # Bytes of a parity error (see termios' PARMRK)

    def _reconfigure_port(self, force_update=False):
        if self.fd is None:
            raise SerialException("Can only operate on a valid file descriptor")

        # if exclusive lock is requested, create it before we modify anything else
        if self._exclusive is not None:
            if self._exclusive:
                try:
                    fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError as msg:
                    raise SerialException(msg.errno, "Could not exclusively lock port {}: {}".format(self._port, msg))
            else:
                fcntl.flock(self.fd, fcntl.LOCK_UN)

        custom_baud = None

        vmin = vtime = 0                # timeout is done via select
        if self._inter_byte_timeout is not None:
            vmin = 1
            vtime = int(self._inter_byte_timeout * 10)
        try:
            orig_attr = termios.tcgetattr(self.fd)
            iflag, oflag, cflag, lflag, ispeed, ospeed, cc = orig_attr
        except termios.error as msg:      # if a port is nonexistent but has a /dev file, it'll fail here
            raise SerialException("Could not configure port: {}".format(msg))
        # set up raw mode / no echo / binary
        cflag |= (termios.CLOCAL | termios.CREAD)
        lflag &= ~(termios.ICANON | termios.ECHO | termios.ECHOE |
                   termios.ECHOK | termios.ECHONL |
                   termios.ISIG | termios.IEXTEN)  # |termios.ECHOPRT
        for flag in ('ECHOCTL', 'ECHOKE'):  # netbsd workaround for Erk
            if hasattr(termios, flag):
                lflag &= ~getattr(termios, flag)

        oflag &= ~(termios.OPOST | termios.ONLCR | termios.OCRNL)
        iflag &= ~(termios.INLCR | termios.IGNCR | termios.ICRNL | termios.IGNBRK)
        if hasattr(termios, 'IUCLC'):
            iflag &= ~termios.IUCLC

        iflag |= termios.PARMRK | termios.INPCK

        # setup baud rate
        try:
            ispeed = ospeed = getattr(termios, 'B{}'.format(self._baudrate))
        except AttributeError:
            try:
                ispeed = ospeed = self.BAUDRATE_CONSTANTS[self._baudrate]
            except KeyError:
                #~ raise ValueError('Invalid baud rate: %r' % self._baudrate)
                # may need custom baud rate, it isn't in our list.
                ispeed = ospeed = getattr(termios, 'B38400')
                try:
                    custom_baud = int(self._baudrate)  # store for later
                except ValueError:
                    raise ValueError('Invalid baud rate: {!r}'.format(self._baudrate))
                else:
                    if custom_baud < 0:
                        raise ValueError('Invalid baud rate: {!r}'.format(self._baudrate))

        # setup char len
        cflag &= ~termios.CSIZE
        if self._bytesize == 8:
            cflag |= termios.CS8
        elif self._bytesize == 7:
            cflag |= termios.CS7
        elif self._bytesize == 6:
            cflag |= termios.CS6
        elif self._bytesize == 5:
            cflag |= termios.CS5
        else:
            raise ValueError('Invalid char len: {!r}'.format(self._bytesize))
        # setup stop bits
        if self._stopbits == serial.STOPBITS_ONE:
            cflag &= ~(termios.CSTOPB)
        elif self._stopbits == serial.STOPBITS_ONE_POINT_FIVE:
            cflag |= (termios.CSTOPB)  # XXX same as TWO.. there is no POSIX support for 1.5
        elif self._stopbits == serial.STOPBITS_TWO:
            cflag |= (termios.CSTOPB)
        else:
            raise ValueError('Invalid stop bit specification: {!r}'.format(self._stopbits))
        # setup parity
        iflag &= ~(termios.ISTRIP)
        if self._parity == serial.PARITY_NONE:
            cflag &= ~(termios.PARENB | termios.PARODD | CMSPAR)
        elif self._parity == serial.PARITY_EVEN:
            cflag &= ~(termios.PARODD | CMSPAR)
            cflag |= (termios.PARENB)
        elif self._parity == serial.PARITY_ODD:
            cflag &= ~CMSPAR
            cflag |= (termios.PARENB | termios.PARODD)
        elif self._parity == serial.PARITY_MARK and CMSPAR:
            cflag |= (termios.PARENB | CMSPAR | termios.PARODD)
        elif self._parity == serial.PARITY_SPACE and CMSPAR:
            cflag |= (termios.PARENB | CMSPAR)
            cflag &= ~(termios.PARODD)
        else:
            raise ValueError('Invalid parity: {!r}'.format(self._parity))
        # setup flow control
        # xonxoff
        if hasattr(termios, 'IXANY'):
            if self._xonxoff:
                iflag |= (termios.IXON | termios.IXOFF)  # |termios.IXANY)
            else:
                iflag &= ~(termios.IXON | termios.IXOFF | termios.IXANY)
        else:
            if self._xonxoff:
                iflag |= (termios.IXON | termios.IXOFF)
            else:
                iflag &= ~(termios.IXON | termios.IXOFF)
        # rtscts
        if hasattr(termios, 'CRTSCTS'):
            if self._rtscts:
                cflag |= (termios.CRTSCTS)
            else:
                cflag &= ~(termios.CRTSCTS)
        elif hasattr(termios, 'CNEW_RTSCTS'):   # try it with alternate constant name
            if self._rtscts:
                cflag |= (termios.CNEW_RTSCTS)
            else:
                cflag &= ~(termios.CNEW_RTSCTS)
        # XXX should there be a warning if setting up rtscts (and xonxoff etc) fails??

        # buffer
        # vmin "minimal number of characters to be read. 0 for non blocking"
        if vmin < 0 or vmin > 255:
            raise ValueError('Invalid vmin: {!r}'.format(vmin))
        cc[termios.VMIN] = vmin
        # vtime
        if vtime < 0 or vtime > 255:
            raise ValueError('Invalid vtime: {!r}'.format(vtime))
        cc[termios.VTIME] = vtime
        # activate settings
        if force_update or [iflag, oflag, cflag, lflag, ispeed, ospeed, cc] != orig_attr:
            termios.tcsetattr(
                self.fd,
                termios.TCSANOW,
                [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])

        # apply custom baud rate, if any
        if custom_baud is not None:
            self._set_special_baudrate(custom_baud)

        if self._rs485_mode is not None:
            self._set_rs485_mode(self._rs485_mode)

    def read(self, size=1):
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
