import enum

from common.helper import byte_to_str
from seatalk.seatalk_datagram import SeatalkDatagram, _ZeroContentClass
from seatalk.seatalk_exceptions import DataValidationException, DataLengthException


class DeviceIdentification2(SeatalkDatagram):
    """
    Special class, which basically holds 3 other classes (depending on length and first half byte)
    """
    seatalk_id = 0xA4
    data_length = -1

    def __init__(self, real_datagram=None):
        SeatalkDatagram.__init__(self)
        self._real_datagram = real_datagram

    def verify_data_length(self, data_len):
        valid_values = [data_gram.data_length for data_gram in (self.BroadCast, self.Answer, self.Termination)]
        if data_len not in valid_values:
            raise DataLengthException(f"{type(self).__name__}: Length not valid. Expected values: {valid_values}, Actual: {data_len}")
        self.data_length = data_len

    def process_datagram(self, first_half_byte, data):
        if self.data_length == 2:
            if first_half_byte == 1:
                data_gram = self.Answer
            else:
                data_gram = self.BroadCast
        else:
            data_gram = self.Termination
        self._real_datagram = data_gram()
        self._real_datagram.process_datagram(first_half_byte, data)

    def get_seatalk_datagram(self):
        return self._real_datagram.get_seatalk_datagram

    class BroadCast(_ZeroContentClass):
        """
        A4  02  00  00 00 Broadcast query to identify all devices on the bus, issued e.g. by C70 plotter
        """
        seatalk_id = 0xA4
        data_length = 2

    class Termination(_ZeroContentClass):
        """
        A4  06  00  00 00 00 00 Termination of request for device identification, sent e.g. by C70 plotter
        """
        seatalk_id = 0xA4
        data_length = 6

    class Answer(SeatalkDatagram):
        """
        A4  12  II  VV WW Device answers identification request
                              II: Unit ID (01=Depth, 02=Speed, 03=Multi, 04=Tridata, 05=Tridata repeater,
                                           06=Wind, 07=WMG, 08=Navdata GPS, 09=Maxview, 0A=Steering compas,
                                           0B=Wind Trim, 0C=Speed trim, 0D=Seatalk GPS, 0E=Seatalk radar ST50,
                                           0F=Rudder angle indicator, 10=ST30 wind, 11=ST30 bidata, 12=ST30 speed,
                                           13=ST30 depth, 14=LCD navcenter, 15=Apelco LCD chartplotter,
                                           16=Analog speedtrim, 17=Analog depth, 18=ST30 compas,
                                           19=ST50 NMEA bridge, A8=ST80 Masterview)
                              VV: Main Software Version
                              WW: Minor Software Version
        """
        seatalk_id = 0xA4
        data_length = 2

        class DeviceID(enum.IntEnum):
            Depth = 0x01
            Speed = 0x02
            Multi = 0x03
            TriData = 0x04
            TriDataRepeater = 0x05
            Wind = 0x06
            WMG = 0x07
            NavdataGPS = 0x08
            Maxview = 0x09
            SteeringCompass = 0x0A
            WindTrim = 0x0B
            SpeedTrim = 0x0C
            SeatalkGPS = 0x0D
            SeatalkRadarST50 = 0x0E
            RudderAngleIndicator = 0x0F
            ST30Wind = 0x10
            ST30BiData = 0x11
            ST30Speed = 0x12
            ST30Depth = 0x13
            LCDNavCenter = 0x14
            ApelcoLCDChartPlotter = 0x15
            AnalogSpeedTrim = 0x16
            AnalogDepth = 0x17
            ST30Compass = 0x18
            ST50NMEABridge = 0x19
            ST80MasterView = 0xA8

        def __init__(self, device_id: DeviceID = None, main_sw_version=None, minor_sw_version=None):
            SeatalkDatagram.__init__(self)
            self.device_id = device_id
            self.main_sw_version = main_sw_version
            self.minor_sw_version = minor_sw_version

        def process_datagram(self, first_half_byte, data):
            if first_half_byte != 0x01:
                raise DataValidationException(f"{type(self).__name__}: First half byte is not 0x01, but {byte_to_str(first_half_byte)}")

            try:
                self.device_id = self.DeviceID(data[0])
            except KeyError as e:
                raise DataValidationException(f"{type(self).__name__}: No corresponding Device to given device-id: {byte_to_str(data[0])}") from e

            self.main_sw_version = data[1]
            self.minor_sw_version = data[2]

        def get_seatalk_datagram(self):
            first_byte = (0x01 << 4) | self.data_length
            # TODO None-values
            return bytearray([self.seatalk_id, first_byte, self.device_id.value, self.main_sw_version, self.minor_sw_version])
