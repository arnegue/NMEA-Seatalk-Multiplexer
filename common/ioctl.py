import os


class IOCTL(object):
    """
    Some simplification of linux' input/output control
    I did not rename the functions to PIP-Standards due to it's unique name in linux itself

    See references:
        https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/ioctl.h
        https://man7.org/linux/man-pages/man2/ioctl.2.html
        https://en.wikipedia.org/wiki/Ioctl
    """
    IOC_NONE = 0
    IOC_WRITE = 1
    IOC_READ = 2

    IOC_NRBITS = 8
    IOC_TYPEBITS = 8
    IOC_SIZEBITS = 14
    IOC_DIRBITS = 2

    IOC_NRSHIFT = 0
    IOC_TYPESHIFT = IOC_NRSHIFT + IOC_NRBITS
    IOC_SIZESHIFT = IOC_TYPESHIFT + IOC_TYPEBITS
    IOC_DIRSHIFT = IOC_SIZESHIFT + IOC_SIZEBITS

    @classmethod
    def _IOC(cls, dir_, type_, nr, size):
        return (dir_ << cls.IOC_DIRSHIFT) | (ord(type_) << cls.IOC_TYPESHIFT) | (nr << cls.IOC_NRSHIFT) | (size << cls.IOC_SIZESHIFT)

    @classmethod
    def IOR(cls, type_, nr, size):
        """
        IO-Read
        """
        return cls._IOC(cls.IOC_READ, type_, nr, size)

    @classmethod
    def IOW(cls, type_, nr, size):
        """
        IO-Write
        """
        return cls._IOC(cls.IOC_WRITE, type_, nr, size)

    @classmethod
    def IOWR(cls, type_, nr, size):
        """
        IO-Write-Read
        """
        return cls._IOC(cls.IOC_READ | cls.IOC_WRITE, type_, nr, size)

    @classmethod
    def call_ioctl(cls, fd, func, arg):
        """
        Finally calls ioctl

        :param fd: file-descriptor
        :param func: function to call
        :param arg: arguments given to function
        """
        if os.name != 'nt':
            import fcntl
            # Similar to call in C:
            #     include <linux/kernel.h>
            #     ioctl(fd, WR_VALUE, (int32_t*) &number);
            fcntl.ioctl(fd, func, arg, True)
