import pytest

import device_io
import seatalk


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
        (bytes([0x00, 0x02, 0x00, 0x00, 0x00]),             seatalk.DepthDatagram),
        (bytes([0x20, 0x01, 0x00, 0x00]),                   seatalk.SpeedDatagram),
        (bytes([0x26, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]), seatalk.SpeedDatagram2),
        (bytes([0x23, 0x01, 0x00, 0x00]),                   seatalk.WaterTemperatureDatagram),
        (bytes([0x27, 0x01, 0x00, 0x00]),                   seatalk.WaterTemperatureDatagram2),
        (bytes([0x30, 0x00, 0x00]),                         seatalk.SetLampIntensityDatagram),
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
    with pytest.raises(seatalk.NotEnoughData):
        await seatalk_device.receive_data_gram()


@pytest.mark.curio
async def test_too_much_data():
    original = bytes([0x00, 0x03, 0x00, 0x00, 0x00, 0x00])
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(original))
    with pytest.raises(seatalk.TooMuchData):
        await seatalk_device.receive_data_gram()


@pytest.mark.curio
async def test_not_recognized():
    original = bytes([0xFF, 0x03, 0x00, 0x00, 0x00, 0x00])
    seatalk_device = seatalk.SeatalkDevice("TestDevice", io_device=TestValueReceiver(original))
    with pytest.raises(seatalk.DataNotRecognizedException):
        await seatalk_device.receive_data_gram()


@pytest.mark.parametrize(("seatalk_datagram", "expected_bytes"), (
        (seatalk.DepthDatagram(depth_m=22.3),      bytes([0x00, 0x02, 0x00, 0xDB, 0x02])),               # 22.3m  -> 73.16f -> 731.6 -> 731  -> 0x02DB -> 0xDB02
        (seatalk.SpeedDatagram(speed_knots=8.31),  bytes([0x20, 0x01, 0x53, 0x00])),                     # 8.3nm  ->        -> 83.1  ->  83  -> 0x0053 -> 0x5300
        (seatalk.SpeedDatagram2(speed_knots=5.19), bytes([0x26, 0x04, 0x07, 0x02, 0x00, 0x00, 0x00])),   # 5.19nm ->        -> 5190  ->      -> 0x0207 -> 0x0702
        (seatalk.WaterTemperatureDatagram(17.2),   bytes([0x23, 0x01, 0x11, 0x3E])),                     # 17.2C  -> 17     ->       ->      -> 0x0011 -> 0x1100
        (seatalk.WaterTemperatureDatagram2(19.2),  bytes([0x27, 0x01, 0xA8, 0x04])),                     # 19.2   ->        -> 119.2 -> 1192 -> 0x04A8 -> 0xA804
        (seatalk.SetLampIntensityDatagram(3),      bytes([0x30, 0x00, 0x0C]))
))
def test_check_datagram_to_seatalk(seatalk_datagram, expected_bytes):
    actual_datagram = seatalk_datagram.get_seatalk_datagram()
    assert expected_bytes == actual_datagram
