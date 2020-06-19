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
        (bytes([0x00, 0x02, 0x00, 0x00, 0x00]),              seatalk.DepthDatagram),
        (bytes([0x20, 0x01, 0x00, 0x00]),                    seatalk.SpeedDatagram),
        (bytes([0x26, 0x04, 0x00, 0x00,  0x00, 0x00, 0x00]), seatalk.SpeedDatagram2),
        (bytes([0x23, 0x01, 0x00, 0x00]),                    seatalk.WaterTemperatureDatagram),
        (bytes([0x27, 0x01, 0x00, 0x00]),                    seatalk.WaterTemperatureDatagram2),
        (bytes([0x30, 0x00, 0x00]),                          seatalk.SetLampIntensityDatagram),
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

