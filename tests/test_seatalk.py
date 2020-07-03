import pytest
import datetime

import device_io
from seatalk import seatalk
from seatalk.seatalk_datagram import *
from helper import bytes_to_str


class TestValueReceiver(device_io.IO):
    def __init__(self, byte_array):
        super().__init__()
        self.bytes = byte_array

    async def _write(self, data):
        raise NotImplementedError()

    async def _read(self, length=1):
        ret_val = self.bytes[:length]
        self.bytes = self.bytes[length:]
        return ret_val


def get_parameters():
    return ("seatalk_datagram", "byte_representation"), (
       (DepthDatagram(depth_m=22.3),                                                                bytes([0x00, 0x02, 0x00, 0xDB, 0x02])),
       (EquipmentIDDatagram1(EquipmentIDDatagram1.Equipments.ST60_Tridata),                         bytes([0x01, 0x05, 0x04, 0xBA, 0x20, 0x28, 0x01, 0x00])),
       (ApparentWindAngleDatagram(256.5),                                                           bytes([0x10, 0x01, 0x01, 0x02])),
       (ApparentWindSpeedDatagram(18.3),                                                            bytes([0x11, 0x01, 0x12, 0x03])),
       (SpeedDatagram(speed_knots=8.31),                                                            bytes([0x20, 0x01, 0x53, 0x00])),
       (TripMileage(6784.12),                                                                       bytes([0x21, 0x02, 0x0C, 0x5A, 0x0A])),
       (TotalMileage(6553),                                                                         bytes([0x22, 0x02, 0xFA, 0xFF, 0x00])),
       (WaterTemperatureDatagram(17.2),                                                             bytes([0x23, 0x01, 0x11, 0x3E])),
       (DisplayUnitsMileageSpeed(DisplayUnitsMileageSpeed.Unit.Kph),                                bytes([0x24, 0x02, 0x00, 0x00, 0x86])),
       (SpeedDatagram2(speed_knots=5.19),                                                           bytes([0x26, 0x04, 0x07, 0x02, 0x00, 0x00, 0x00])),
       (WaterTemperatureDatagram2(19.2),                                                            bytes([0x27, 0x01, 0xA8, 0x04])),
       (SetLampIntensity1(3),                                                                       bytes([0x30, 0x00, 0x0C])),
       (CodeLockData(x=15, y=248, z=1),                                                             bytes([0x38, 0xF1, 0xF8, 0x01])),
       (CancelMOB(),                                                                                bytes([0x36, 0x00, 0x01])),
       (Date(date=datetime.date(year=2019, month=10, day=31)),                                      bytes([0x56, 0xA1, 0x1F, 0x13])),
       (SpeedOverGround(26.9),                                                                      bytes([0x52, 0x01, 0x0D, 0x01])),
       (KeyStroke1(key=KeyStroke1.Key.M1M10PortTack, increment_decrement=1),                        bytes([0x55, 0x11, 0x21, 0xDE])),
       (SatInfo(0x1, 0x94),                                                                         bytes([0x57, 0x10, 0x94])),
       (CountDownTimer(hours=9, minutes=59, seconds=59, mode=CountDownTimer.CounterMode.CountDown), bytes([0x59, 0x22, 0x3B, 0x3B, 0x49])),
       (E80Initialization(),                                                                        bytes([0x61, 0x03, 0x03, 0x00, 0x00, 0x00])),
       (SelectFathom(),                                                                             bytes([0x65, 0x00, 0x02])),
       (WindAlarm(WindAlarm.Alarm.AngleLow, WindAlarm.Alarm.SpeedHigh),                             bytes([0x66, 0x00, 0x81])),
       (AlarmAcknowledgement(AlarmAcknowledgement.AcknowledgementAlarms.DeepWaterAlarm),            bytes([0x68, 0x21, 0x01, 0x00])),
       (EquipmentIDDatagram2(EquipmentIDDatagram2.Equipments.ST60_Log),                             bytes([0x6C, 0x05, 0x05, 0x70, 0x99, 0x10, 0x28, 0x2D])),
       (ManOverBoard(),                                                                             bytes([0x6E, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
       (SetLampIntensity2(1),                                                                       bytes([0x80, 0x00, 0x04])),
       (KeyStroke2(key=KeyStroke2.Key.StandbyAutoGT1S),                                             bytes([0x86, 0x01, 0x63, 0x9C])),
       (SetResponseLevel(response_level=SetResponseLevel.Deadband.Minimum),                         bytes([0x87, 0x00, 0x02])),
       (DeviceIdentification1(DeviceIdentification1.DeviceID.ST600R),                               bytes([0x90, 0x00, 0x02])),
       (SetRudderGain(3),                                                                           bytes([0x91, 0x00, 0x03])),
       (EnterAPSetup(),                                                                             bytes([0x93, 0x00, 0x00])),
    )


@pytest.mark.curio
@pytest.mark.parametrize(*get_parameters())
async def test_correct_recognition(seatalk_datagram, byte_representation):
    """
    Tests if "received" bytes result in a correct Datagram-Recognition (no direct value check here)
    """
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(byte_representation))
    recognized_datagram = await seatalk_device.receive_data_gram()
    assert isinstance(recognized_datagram, type(seatalk_datagram))


@pytest.mark.curio
async def test_not_enough_data():
    original = bytes([0x00, 0x01, 0x00, 0x00])
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(original))
    with pytest.raises(NotEnoughData):
        await seatalk_device.receive_data_gram()


@pytest.mark.curio
async def test_too_much_data():
    original = bytes([0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(original))
    with pytest.raises(TooMuchData):
        await seatalk_device.receive_data_gram()


@pytest.mark.curio
async def test_not_recognized():
    original = bytes([0xFF, 0x03, 0x00, 0x00, 0x00, 0x00])
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(original))
    with pytest.raises(seatalk.DataNotRecognizedException):
        await seatalk_device.receive_data_gram()


@pytest.mark.parametrize(*get_parameters())
def test_check_datagram_to_seatalk(seatalk_datagram, byte_representation):
    actual_datagram = seatalk_datagram.get_seatalk_datagram()
    assert bytes_to_str(byte_representation) == bytes_to_str(actual_datagram)
    assert byte_representation == actual_datagram


@pytest.mark.parametrize("seatalk_datagram_instance", (
    EquipmentIDDatagram1(9),
    SetLampIntensity1(9)
))
def test_two_way_maps_validations(seatalk_datagram_instance):
    with pytest.raises(DataValidationException):
        seatalk_datagram_instance.get_seatalk_datagram()


@pytest.mark.curio
async def test_raw_seatalk():
    reader = device_io.File(path="./test_data/seatalk_raw.hex", encoding=False)
    await reader.initialize()
    seatalk_device = seatalk.SeatalkDevice("RawSeatalkFileDevice", io_device=reader)
    for i in range(1000):
        try:
            result = await seatalk_device.receive_data_gram()
        except seatalk.SeatalkException as e:
            print(e)
        else:
            if isinstance(result, nmea_datagram.NMEADatagram):
                print(result.get_nmea_sentence())
            print(bytes_to_str(result.get_seatalk_datagram()))


def get_device_identification_2_parameters():
    return ("seatalk_datagram", "byte_representation"), (
        (DeviceIdentification2.BroadCast(),     bytes([0xA4, 0x02, 0x00, 0x00, 0x00])),
        (DeviceIdentification2.Termination(),   bytes([0xA4, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
        (DeviceIdentification2.Answer(DeviceIdentification2.Answer.DeviceID.RudderAngleIndicator, 0x34, 0x89), bytes([0xA4, 0x12, 0x0F, 0x34, 0x89]))
    )


@pytest.mark.curio
@pytest.mark.parametrize(*get_device_identification_2_parameters())
async def test_correct_recognition_device_identification_2(seatalk_datagram, byte_representation):
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(byte_representation))
    recognized_datagram = await seatalk_device.receive_data_gram()
    assert isinstance(recognized_datagram._real_datagram, type(seatalk_datagram))


@pytest.mark.parametrize(*get_device_identification_2_parameters())
def test_check_datagram_to_seatalk_device_identification_2(seatalk_datagram, byte_representation):
    test_check_datagram_to_seatalk(seatalk_datagram, byte_representation)


# TODO test instantiate seatalk-datagrams with None values. test get-seatalk-datagram