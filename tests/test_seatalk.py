import pytest

import device_io
from seatalk import seatalk, seatalk_datagram


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


@pytest.mark.curio
@pytest.mark.parametrize(("original", "data_gram_type"), (
        (bytes([0x00, 0x02, 0x00, 0x00, 0x00]),                   seatalk_datagram.DepthDatagram),
        (bytes([0x20, 0x01, 0x00, 0x00]),                         seatalk_datagram.SpeedDatagram),
        (bytes([0x26, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]),       seatalk_datagram.SpeedDatagram2),
        (bytes([0x23, 0x01, 0x00, 0x00]),                         seatalk_datagram.WaterTemperatureDatagram),
        (bytes([0x27, 0x01, 0x00, 0x00]),                         seatalk_datagram.WaterTemperatureDatagram2),
        (bytes([0x30, 0x00, 0x00]),                               seatalk_datagram.SetLampIntensityDatagram),
        (bytes([0x01, 0x05, 0xFF, 0xFF, 0xFF, 0xD0, 0x00, 0x00]), seatalk_datagram.EquipmentIDDatagram),
        (bytes([0x36, 0x00, 0x01]),                               seatalk_datagram.CancelMOB),
))
async def test_correct_recognition(original, data_gram_type):
    """
    Tests if "received" bytes are correctly recognized
    """
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(original))
    recognized_datagram = await seatalk_device.receive_data_gram()
    assert isinstance(recognized_datagram, data_gram_type)


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


@pytest.mark.parametrize(("seatalk_datagram", "expected_bytes"), (
        (seatalk_datagram.DepthDatagram(depth_m=22.3),      bytes([0x00, 0x02, 0x00, 0xDB, 0x02])),               # 22.3m  -> 73.16f -> 731.6 -> 731  -> 0x02DB -> 0xDB02
        (seatalk_datagram.SpeedDatagram(speed_knots=8.31),  bytes([0x20, 0x01, 0x53, 0x00])),                     # 8.3nm  ->        -> 83.1  ->  83  -> 0x0053 -> 0x5300
        (seatalk_datagram.SpeedDatagram2(speed_knots=5.19), bytes([0x26, 0x04, 0x07, 0x02, 0x00, 0x00, 0x00])),   # 5.19nm ->        -> 5190  ->      -> 0x0207 -> 0x0702
        (seatalk_datagram.WaterTemperatureDatagram(17.2),   bytes([0x23, 0x01, 0x11, 0x3E])),                     # 17.2C  -> 17     ->       ->      -> 0x0011 -> 0x1100
        (seatalk_datagram.WaterTemperatureDatagram2(19.2),  bytes([0x27, 0x01, 0xA8, 0x04])),                     # 19.2   ->        -> 119.2 -> 1192 -> 0x04A8 -> 0xA804
        (seatalk_datagram.SetLampIntensityDatagram(3),      bytes([0x30, 0x00, 0x0C])),
        (seatalk_datagram.EquipmentIDDatagram(seatalk_datagram.EquipmentIDDatagram.Equipments.ST60_Tridata),      bytes([0x01, 0x05, 0x04, 0xBA, 0x20, 0x28, 0x01, 0x00])),
        (seatalk_datagram.CancelMOB(),                      bytes([0x36, 0x00, 0x01]))
))
def test_check_datagram_to_seatalk(seatalk_datagram, expected_bytes):
    actual_datagram = seatalk_datagram.get_seatalk_datagram()
    assert expected_bytes == actual_datagram


@pytest.mark.parametrize("seatalk_datagram_instance", (
    seatalk_datagram.EquipmentIDDatagram(9),
    seatalk_datagram.SetLampIntensityDatagram(9)
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
