import ctypes
import os
import time
import threading
from abc import ABCMeta

from common.ioctl import IOCTL
from logger import logger


class WatchdogError(Exception):
    pass


class Watchdog(object, metaclass=ABCMeta):
    def __init__(self, timeout=None):
        self.timeout = timeout

    def start(self):
        """
        Arms watchdog
        """
        raise NotImplementedError()

    def reset(self):
        """
        Resets watchdog timeout
        """
        raise NotImplementedError()

    def exit(self):
        """
        Gracefully disarms watchdog
        """
        logger.info("Shutting down watchdog")

    @classmethod
    def get_watchdog(cls):
        if os.name == 'nt':
            return _SoftwareWatchdog
        else:
            return _LinuxWatchdog

    def get_timeout(self):
        return self.timeout


class _SoftwareWatchdog(Watchdog):
    """
    Watchdog implementation which manually triggers reboot of system. If python or the OS hangs, there is no way this
    watchdog will notice it. But at least if some
    """
    def __init__(self, timeout):
        super().__init__(timeout=timeout)
        self._current_reset_value = 0
        self.reset()
        self._shutdown = False
        self._thread = None

    def start(self):
        if self._thread:
            raise WatchdogError("There is already a watchdog running")
        self._thread = threading.Thread(target=self._routine)
        self._thread.start()

    def reset(self):
        self._current_reset_value = self.timeout

    def exit(self):
        super().exit()
        self._shutdown = True
        self._thread.join()

    def _routine(self):
        """
        Watches every second if the timer runs out
        :return:
        """
        while self._current_reset_value > 0 and self._shutdown is False:
            time.sleep(1)
            logger.info(str(self._current_reset_value))
            self._current_reset_value -= 1

        if self._shutdown:
            logger.info("Shutdown watchdog")
        else:
            logger.error("Watchdog timeout. Initiating restart")
            # Should work on unix and posix systems
            os.system("shutdown -t 0 -r -f")


class _LinuxWatchdog(Watchdog):
    """
    Watchdog-Feeding class. Feeds watchdog at /dev/watchdog
    See README.MD
    """
    WATCHDOG_FILE = "/dev/watchdog"
    WATCHDOG_IOCTL_BASE = 'W'

    def __init__(self, timeout=None):
        super().__init__(timeout=timeout)
        self._wd_fd = None  # WatchDog FileDescriptor

    def get_timeout(self):
        timeout = ctypes.c_int()
        WDIOC_GETTIMEOUT = IOCTL.IOR(self.WATCHDOG_IOCTL_BASE, 7, ctypes.sizeof(timeout))

        IOCTL.call_ioctl(self._wd_fd, WDIOC_GETTIMEOUT, timeout)
        return timeout.value

    def get_support(self):
        class SupportStruct(ctypes.Structure):
            """
            see "struct watchdog_info" in watchdog.h
            """
            _fields_ = [
                ("options", ctypes.c_uint32),
                ("firmware_version", ctypes.c_uint32),
                ("identity", ctypes.c_uint8 * 32)
            ]

        watchdog_info = SupportStruct()
        WDIOC_GETSUPPORT = IOCTL.IOR(self.WATCHDOG_IOCTL_BASE, 0, ctypes.sizeof(watchdog_info))
        IOCTL.call_ioctl(self._wd_fd, WDIOC_GETSUPPORT, watchdog_info)
        watchdog_identity = ""
        for i in watchdog_info.identity:
            watchdog_identity += chr(i)
        watchdog_identity = watchdog_identity.rstrip('\x00')
        # e.g. "Watchdog-Identity: Broadcom BCM2835 Watchdog timer, Options: 33152, FirmwareVersion: 0"
        logger.info(f"Watchdog-Identity: {watchdog_identity}, Options: {watchdog_info.options}, FirmwareVersion: {watchdog_info.firmware_version}")

    def set_timeout(self, timeout):
        c_timeout = ctypes.c_int(int(timeout))
        WDIOC_SETTIMEOUT = IOCTL.IOWR(self.WATCHDOG_IOCTL_BASE, 6, ctypes.sizeof(c_timeout))

        try:
            IOCTL.call_ioctl(self._wd_fd, WDIOC_SETTIMEOUT, c_timeout)
        except OSError as e:  # Usually occurs if timeout is set too high
            raise WatchdogError(f"Couldn't set a timeout of {timeout} seconds.") from e

        if self.get_timeout() != timeout:
            raise WatchdogError(f"Couldn't set timeout of {timeout} seconds")

    def start(self):
        self._wd_fd = open(self.__class__.WATCHDOG_FILE, "w")
        logger.info("Armed watchdog")
        if self.timeout is None:
            self.timeout = self.get_timeout()
        else:
            self.set_timeout(self.timeout)
        logger.info(f"Watchdog timeout is at {self.timeout} seconds")

    def reset(self):
        """
        Most important function that feeds the watchdog so it won't reset the system
        """
        self._wd_fd.write("\0")  # I think the character doesn't matter as long as it's not 'V' (see exit_watchdog)

    def exit(self, magic_close: bool = True):
        """
        Exits the watchdog.

        :param magic_close: if set the watchdog will be disabled, so that it won't trigger a restart
        """
        super().exit()
        if magic_close:
            self._wd_fd.write("V")
        self._wd_fd.close()
