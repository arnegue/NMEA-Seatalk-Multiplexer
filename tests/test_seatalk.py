import pytest
import datetime

import device_io
from seatalk import seatalk, seatalk_datagram
from helper import  bytes_to_str


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
       (seatalk_datagram.DepthDatagram(depth_m=22.3),      bytes([0x00, 0x02, 0x00, 0xDB, 0x02])),
       (seatalk_datagram.EquipmentIDDatagram1(seatalk_datagram.EquipmentIDDatagram1.Equipments.ST60_Tridata), bytes([0x01, 0x05, 0x04, 0xBA, 0x20, 0x28, 0x01, 0x00])),
       (seatalk_datagram.ApparentWindAngleDatagram(256.5), bytes([0x10, 0x01, 0x01, 0x02])),
       (seatalk_datagram.ApparentWindSpeedDatagram(18.3),  bytes([0x11, 0x01, 0x12, 0x03])),
       (seatalk_datagram.SpeedDatagram(speed_knots=8.31),  bytes([0x20, 0x01, 0x53, 0x00])),
       (seatalk_datagram.TripMileage(6784.12),             bytes([0x21, 0x02, 0x0C, 0x5A, 0x0A])),
       (seatalk_datagram.TotalMileage(6553),               bytes([0x22, 0x02, 0xFA, 0xFF, 0x00])),
       (seatalk_datagram.WaterTemperatureDatagram(17.2),   bytes([0x23, 0x01, 0x11, 0x3E])),
       (seatalk_datagram.SpeedDatagram2(speed_knots=5.19), bytes([0x26, 0x04, 0x07, 0x02, 0x00, 0x00, 0x00])),
       (seatalk_datagram.WaterTemperatureDatagram2(19.2),  bytes([0x27, 0x01, 0xA8, 0x04])),
       (seatalk_datagram.SetLampIntensity1(3),             bytes([0x30, 0x00, 0x0C])),
       (seatalk_datagram.CodeLockData(x=15, y=248, z=1),   bytes([0x38, 0xF1, 0xF8, 0x01])),
       (seatalk_datagram.CancelMOB(),                      bytes([0x36, 0x00, 0x01])),
       (seatalk_datagram.Date(date=datetime.date(year=2019, month=10, day=31)), bytes([0x56, 0xA1, 0x1F, 0x13])),
       (seatalk_datagram.SpeedOverGround(26.9),            bytes([0x52, 0x01, 0x0D, 0x01])),
       (seatalk_datagram.SatInfo(0x1, 0x94),               bytes([0x57, 0x10, 0x94])),
       (seatalk_datagram.WindAlarm(seatalk_datagram.WindAlarm.Alarm.AngleLow, seatalk_datagram.WindAlarm.Alarm.SpeedHigh), bytes([0x66, 0x00, 0x81])),
       (seatalk_datagram.AlarmAcknowledgement(seatalk_datagram.AlarmAcknowledgement.AcknowledgementAlarms.DeepWaterAlarm), bytes([0x68, 0x21, 0x01, 0x00])),
       (seatalk_datagram.EquipmentIDDatagram2(seatalk_datagram.EquipmentIDDatagram2.Equipments.ST60_Log), bytes([0x6C, 0x05, 0x05, 0x70, 0x99, 0x10, 0x28, 0x2D])),
       (seatalk_datagram.ManOverBoard(),                   bytes([0x6E, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
       (seatalk_datagram.SetLampIntensity2(1),             bytes([0x80, 0x00, 0x04])),
       (seatalk_datagram.DeviceIdentification(seatalk_datagram.DeviceIdentification.DeviceID.ST600R), bytes([0x90, 0x00, 0x02])),
       (seatalk_datagram.SetRudderGain(3),                 bytes([0x91, 0x00, 0x03])),
       (seatalk_datagram.EnterAPSetup(),                   bytes([0x93, 0x00, 0x00])),
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
    with pytest.raises(seatalk_datagram.NotEnoughData):
        await seatalk_device.receive_data_gram()


@pytest.mark.curio
async def test_too_much_data():
    original = bytes([0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(original))
    with pytest.raises(seatalk_datagram.TooMuchData):
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
    seatalk_datagram.EquipmentIDDatagram1(9),
    seatalk_datagram.SetLampIntensity1(9)
))
def test_two_way_maps_validations(seatalk_datagram_instance):
    with pytest.raises(seatalk_datagram.DataValidationException):
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
            print(result.get_nmea_sentence())


def get_device_identification_2_parameters():
    return ("seatalk_datagram", "byte_representation"), (
        (seatalk_datagram.DeviceIdentification2.BroadCast(),     bytes([0xA4, 0x02, 0x00, 0x00, 0x00])),
        (seatalk_datagram.DeviceIdentification2.Termination(),   bytes([0xA4, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])),
        (seatalk_datagram.DeviceIdentification2.Answer(seatalk_datagram.DeviceIdentification2.Answer.DeviceID.RudderAngleIndicator, 0x34, 0x89), bytes([0xA4, 0x12, 0x0F, 0x34, 0x89]))
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
