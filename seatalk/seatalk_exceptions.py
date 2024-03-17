from nmea import nmea_datagram
from common.helper import byte_to_str
import logger


class SeatalkException(nmea_datagram.NMEAError):
    """
    Any Exception concerning Seatalk
    """


class NoCorrespondingNMEASentence(SeatalkException):
    """
    Exception if Seatalk-Datagram doesn't have a belonging NMEA-Sentence (e.g. some commands for Display-Light)
    """
    def __init__(self, data_gram):
        logger.info(f"{type(data_gram).__name__}: There is no corresponding NMEADatagram")


class DataValidationException(SeatalkException):
    """
    Errors happening when converting raw Seatalk-Data
    """


class DataLengthException(DataValidationException):
    """
    Exceptions happening in validation if length is incorrect
    """


class NotEnoughData(DataLengthException):
    def __init__(self, data_gram, expected, actual):
        super().__init__(f"{type(data_gram).__name__}: Not enough data arrived. Expected: {expected}, actual {actual}")


class TooMuchData(DataLengthException):
    def __init__(self, data_gram, expected, actual):
        super().__init__(f"{type(data_gram).__name__}: Too much data arrived. Expected: {expected}, actual {actual}")


class DataNotRecognizedException(DataValidationException):
    """
    This exception is getting raised if the Command-Byte is not recognized
    """
    def __init__(self, device_name, command_byte):
        super().__init__(f"{device_name}: Unknown command-byte: {byte_to_str(command_byte)}")
