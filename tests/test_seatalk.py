import pytest
import curio
import datetime

import device_io
from common.helper import UnitConverter
from common.parity_serial import ParityException
from nmea import nmea_datagram
from seatalk import *
from seatalk.datagrams.seatalk_datagram import *
from common import helper


class NoneReadWriter(device_io.IO):
    async def _write(self, data):
        await curio.sleep(0)

    async def _read(self, length=1):
        await curio.sleep(0)
        return bytes(length)


class TestValueReceiver(device_io.IO):
    def __init__(self, byte_array):
        super().__init__()
        self.bytes = byte_array
        self._parity_error_send = False

    async def _write(self, data):
        raise NotImplementedError()

    async def _read(self, length=1):
        if length != 1:
            raise Exception(f"Length {length} not supported")

        if not self._parity_error_send:
            self._parity_error_send = True
            raise ParityException()

        ret_val = self.bytes[:length]
        self.bytes = self.bytes[length:]
        return ret_val


def get_parameters():
    return ("seatalk_datagram", "byte_representation"), (
       (Depth(depth_m=UnitConverter.feet_to_meter(465.8)),                                              bytes([0x00, 0x02, 0x00, 0x32, 0x12])),
       (EquipmentID1(EquipmentID1.Equipments.ST60_Tridata),                                             bytes([0x01, 0x05, 0x04, 0xBA, 0x20, 0x28, 0x01, 0x00])),
       (ApparentWindAngle(179),                                                                         bytes([0x10, 0x01, 0x01, 0x66])),
       (ApparentWindSpeed(18.3),                                                                        bytes([0x11, 0x01, 0x12, 0x03])),
       (Speed1(speed_knots=132.2),                                                                      bytes([0x20, 0x01, 0x2A, 0x05])),
       (TripMileage(6784.12),                                                                           bytes([0x21, 0x02, 0x0C, 0x5A, 0x0A])),
       (TotalMileage(6553),                                                                             bytes([0x22, 0x02, 0xFA, 0xFF, 0x00])),
       (WaterTemperature1(temperature_c=17.2, sensor_defective=True),                                   bytes([0x23, 0x41, 0x11, 0x3E])),
       (DisplayUnitsMileageSpeed(DisplayUnitsMileageSpeed.Unit.Kph),                                    bytes([0x24, 0x02, 0x00, 0x00, 0x86])),
       (TotalTripLog(total_miles=7886.6, trip_miles=6206.3),                                            bytes([0x25, 0x14, 0x12, 0x34, 0x56, 0x78, 0x09])),
       (Speed2(speed_knots=132.19),                                                                     bytes([0x26, 0x04, 0xA3, 0x33, 0x00, 0x00, 0x00])),
       (WaterTemperature2(39.8),                                                                        bytes([0x27, 0x01, 0xF2, 0x01])),
       (SetLampIntensity1(3),                                                                           bytes([0x30, 0x00, 0x0C])),
       (CodeLockData(x=15, y=248, z=1),                                                                 bytes([0x38, 0xF1, 0xF8, 0x01])),
       (CancelMOB(),                                                                                    bytes([0x36, 0x00, 0x01])),
       (LatitudePosition(position=PartPosition(degrees=53, minutes=57, direction=Orientation.North)),   bytes([0x50, 0x02, 0x35, 0x44, 0x16])),
       (LongitudePosition(position=PartPosition(degrees=8, minutes=28.21, direction=Orientation.East)), bytes([0x51, 0x02, 0x08, 0x05, 0x8B])),
       (SpeedOverGround(123.4),                                                                         bytes([0x52, 0x01, 0xD2, 0x04])),
       (CourseOverGround(180),                                                                          bytes([0x53, 0x20, 0x00])),
       (GMT_Time(hours=23, minutes=6, seconds=44),                                                      bytes([0x54, 0xC1, 0x1A, 0x17])),
       (KeyStroke1(key=KeyStroke1.Key.M1M10PortTack, increment_decrement=1),                            bytes([0x55, 0x11, 0x21, 0xDE])),
       (Date(date=datetime.date(year=2019, month=10, day=31)),                                          bytes([0x56, 0xA1, 0x1F, 0x13])),
       (SatInfo(0x1, 0x94),                                                                             bytes([0x57, 0x10, 0x94])),
       (Position(position=helper.Position(
           latitude=PartPosition(degrees=53, minutes=57, direction=Orientation.North),
           longitude=PartPosition(degrees=8, minutes=28.21, direction=Orientation.East))),              bytes([0x58, 0x25, 0x35, 0xDE, 0xA8, 0x08, 0x6E, 0x32])),
       (CountdownTimer(hours=9, minutes=59, seconds=59, mode=CountdownTimer.CounterMode.CountDown),     bytes([0x59, 0x22, 0x3B, 0x3B, 0x49])),
       (E80Initialization(),                                                                            bytes([0x61, 0x03, 0x03, 0x00, 0x00, 0x00])),
       (SelectFathom(),                                                                                 bytes([0x65, 0x00, 0x02])),
       (WindAlarm(WindAlarm.Alarm.AngleLow, WindAlarm.Alarm.SpeedHigh),                                 bytes([0x66, 0x00, 0x81])),
       (AlarmAcknowledgement(AlarmAcknowledgement.AcknowledgementAlarms.DeepWaterAlarm),                bytes([0x68, 0x21, 0x01, 0x00])),
       (EquipmentID2(EquipmentID2.Equipments.ST60_Log),                                                 bytes([0x6C, 0x05, 0x05, 0x70, 0x99, 0x10, 0x28, 0x2D])),
       (ManOverBoard(),                                                                                 bytes([0x6E, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
       (SetLampIntensity2(1),                                                                           bytes([0x80, 0x00, 0x04])),
       (CourseComputerSetup(CourseComputerSetup.MessageTypes.SetupFinished),                            bytes([0x81, 0x00, 0x00])),
       (CourseComputerSetup(CourseComputerSetup.MessageTypes.Setup),                                    bytes([0x81, 0x01, 0x00, 0x00])),
       (KeyStroke2(key=KeyStroke2.Key.StandbyAutoGT1S),                                                 bytes([0x86, 0x01, 0x63, 0x9C])),
       (SetResponseLevel(response_level=SetResponseLevel.Deadband.Minimum),                             bytes([0x87, 0x00, 0x02])),
       (DeviceIdentification1(DeviceIdentification1.DeviceID.ST600R),                                   bytes([0x90, 0x00, 0x02])),
       (SetRudderGain(3),                                                                               bytes([0x91, 0x00, 0x03])),
       (EnterAPSetup(),                                                                                 bytes([0x93, 0x00, 0x00])),
       (CompassVariation(-28),                                                                          bytes([0x99, 0x00, 0xE4])),
       (TargetWaypointName("0058"),                                                                     bytes([0x82, 0x05, 0x00, 0xFF, 0x50, 0xAF, 0x20, 0xDF])),
    )


def get_device_identification_2_parameters():
    return ("seatalk_datagram", "byte_representation"), (
        (DeviceIdentification2.BroadCast(),     bytes([0xA4, 0x02, 0x00, 0x00, 0x00])),
        (DeviceIdentification2.Termination(),   bytes([0xA4, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
        (DeviceIdentification2.Answer(DeviceIdentification2.Answer.DeviceID.RudderAngleIndicator, 0x34, 0x89), bytes([0xA4, 0x12, 0x0F, 0x34, 0x89]))
    )


class TestSeatalkDatagram:
    test_array = bytes([0x13, 0x57])
    test_result = 22291

    def test_set_value(self):
        result = SeatalkDatagram.set_value(self.test_result)
        assert self.test_array == result

    def test_get_value(self):
        result = SeatalkDatagram.get_value(self.test_array)
        assert self.test_result == result

    @pytest.mark.curio
    @pytest.mark.parametrize(*get_parameters())
    async def test_correct_recognition(self, seatalk_datagram, byte_representation):
        """
        Tests if "received" bytes result in a correct Datagram-Recognition (no direct value check here)
        """
        seatalk_device = seatalk.SeatalkDevice(name="TestDevice", io_device=TestValueReceiver(byte_representation))
        datagram = await seatalk_device._receive_datagram()
        recognized_datagram = seatalk_device.parse_datagram(datagram)
        assert isinstance(recognized_datagram, type(seatalk_datagram))

    @pytest.mark.curio
    async def test_not_enough_data(self):
        original = bytes([0x00, 0x01, 0x00, 0x00])
        seatalk_device = seatalk.SeatalkDevice(name="TestDevice", io_device=TestValueReceiver(original))
        with pytest.raises(NotEnoughData):
            datagram = await seatalk_device._receive_datagram()
            seatalk_device.parse_datagram(datagram)

    @pytest.mark.curio
    async def test_too_much_data(self):
        original = bytes([0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
        seatalk_device = seatalk.SeatalkDevice(name="TestDevice", io_device=TestValueReceiver(original))
        with pytest.raises(TooMuchData):
            datagram = await seatalk_device._receive_datagram()
            seatalk_device.parse_datagram(datagram)

    @pytest.mark.curio
    async def test_not_recognized(self):
        original = bytes([0xFF, 0x03, 0x00, 0x00, 0x00, 0x00])
        seatalk_device = seatalk.SeatalkDevice(name="TestDevice", io_device=TestValueReceiver(original))
        with pytest.raises(seatalk.DataNotRecognizedException):
            datagram = await seatalk_device._receive_datagram()
            seatalk_device.parse_datagram(datagram)

    @pytest.mark.parametrize(*get_parameters())
    def test_check_datagram_to_seatalk(self, seatalk_datagram, byte_representation):
        actual_datagram = seatalk_datagram.get_seatalk_datagram()
        assert bytes_to_str(actual_datagram) == bytes_to_str(byte_representation)
        assert actual_datagram == byte_representation

    @pytest.mark.parametrize("seatalk_datagram_instance", (
        EquipmentID1(9),
        SetLampIntensity1(9)
    ))
    def test_two_way_maps_validations(self, seatalk_datagram_instance):
        with pytest.raises(DataValidationException):
            seatalk_datagram_instance.get_seatalk_datagram()

    @pytest.mark.curio
    @pytest.mark.skip("Seatalk now only works with parity-errors, which are not supported in other device-ios")
    async def test_raw_seatalk(self):
        reader = device_io.File(path="./tests/test_data/seatalk_raw.hex", encoding=False) # TODO differentiate between simple seatalk-error and
        await reader.initialize()
        seatalk_device = seatalk.SeatalkDevice(name="RawSeatalkFileDevice", io_device=reader)
        for i in range(1000):
            try:
                result = await seatalk_device._receive_datagram()
            except seatalk.SeatalkException as e:
                print(e)
            else:
                if isinstance(result, nmea_datagram.NMEADatagram):
                    print(result.get_nmea_sentence())
                print(bytes_to_str(result.get_seatalk_datagram()))

    @pytest.mark.curio
    @pytest.mark.parametrize(*get_device_identification_2_parameters())
    async def test_correct_recognition_device_identification_2(self, seatalk_datagram, byte_representation):
        seatalk_device = seatalk.SeatalkDevice(name="TestDevice", io_device=TestValueReceiver(byte_representation))
        datagram = await seatalk_device._receive_datagram()
        recognized_datagram = seatalk_device.parse_datagram(datagram)
        assert isinstance(recognized_datagram._real_datagram, type(seatalk_datagram))

    @pytest.mark.parametrize(*get_device_identification_2_parameters())
    def test_check_datagram_to_seatalk_device_identification_2(self, seatalk_datagram, byte_representation):
        self.test_check_datagram_to_seatalk(seatalk_datagram, byte_representation)

    # def get_all_seatalk_datagrams(self):
    #    seatalk_device = seatalk.SeatalkDevice(name="TestDevice", io_device=NoneReadWriter())
    #    return "datagram", (seatalk_device._seatalk_datagram_map.values())

    # @pytest.mark.parametrize(*get_all_seatalk_datagrams())
    # def test_get_none_seatalk_messages(datagram):
    #     """
    #     instantiate seatalk-datagrams with None values. test get-seatalk-datagram
    #     """
    #     datagram().get_seatalk_datagram()
