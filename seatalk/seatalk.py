import inspect
from abc import ABCMeta

from common.helper import get_numeric_byte_value, byte_to_str, bytes_to_str
import logger
from device import TaskDevice
from nmea import nmea_datagram
import seatalk
import seatalk.datagrams.seatalk_datagram  # TODO remove when #1 is finished
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import SeatalkException, NoCorrespondingNMEASentence, DataNotRecognizedException


class SeatalkDevice(TaskDevice, metaclass=ABCMeta):
    _seatalk_datagram_map = dict()

    class RawSeatalkLogger(TaskDevice.RawDataLogger):
        def __init__(self, device_name):
            super().__init__(device_name=device_name, terminator="\n")

        def write_raw_seatalk(self, rec, attribute, data, ingoing):
            data_gram_bytes = bytearray()
            for value in rec, attribute, data:
                if isinstance(value, bytearray):
                    data_gram_bytes += value
                else:
                    data_gram_bytes.append(value)
            self.info(data=bytes_to_str(data_gram_bytes), ingoing=ingoing)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if len(self.__class__._seatalk_datagram_map) == 0:
            for name, obj in inspect.getmembers(seatalk.datagrams.seatalk_datagram):  # TODO remove when #1 is finished
                # Abstract, non-private SeatalkDatagrams
                if inspect.isclass(obj) and issubclass(obj, SeatalkDatagram) and not inspect.isabstract(obj) and obj.__name__[0] != '_':
                    self.__class__._seatalk_datagram_map[obj.seatalk_id] = obj

            for name, obj in inspect.getmembers(seatalk):
                # Abstract, non-private SeatalkDatagrams
                if inspect.isclass(obj) and issubclass(obj, SeatalkDatagram) and not inspect.isabstract(obj) and obj.__name__[0] != '_':
                    self.__class__._seatalk_datagram_map[obj.seatalk_id] = obj

    def _get_data_logger(self):
        return self.RawSeatalkLogger(self._name)

    async def _read_from_io_task(self):
        while True:
            try:
                data_gram = await self.receive_data_gram()

                # Now check if there is a corresponding NMEA-Datagram (e.g. SetLampIntensityDatagram does not have one)
                if isinstance(data_gram, nmea_datagram.NMEADatagram):
                    await self._read_queue.put(data_gram)
                else:
                    raise NoCorrespondingNMEASentence(data_gram)
            except SeatalkException:
                pass
            finally:
                await self._check_flush()

    async def receive_data_gram(self):
        """
        For more info: http://www.thomasknauf.de/seatalk.htm
        """
        cmd_byte = int()
        attribute = bytearray()
        data_bytes = bytearray()
        try:
            # Get Command-Byte
            cmd_byte = get_numeric_byte_value(await self._io_device.read(1))
            if cmd_byte in self.__class__._seatalk_datagram_map:
                # Extract datagram and instantiate it
                data_gram = self.__class__._seatalk_datagram_map[cmd_byte]()

                # Receive attribute byte which tells how long the message will be and maybe some additional info important to the SeatalkDatagram
                attribute = await self._io_device.read(1)
                attribute_nr = get_numeric_byte_value(attribute)
                data_length = attribute_nr & 0x0F  # DataLength according to seatalk-datagram. length of 0 means 1 byte of data
                attr_data = (attribute_nr & 0xF0) >> 4
                # Verifies length (will raise exception before actually receiving data which won't be needed
                data_gram.verify_data_length(data_length)

                # At this point data_length is okay, finally receive it and progress whole datagram
                data_bytes += await self._io_device.read(data_length + 1)
                data_gram.process_datagram(first_half_byte=attr_data, data=data_bytes)
                # No need to verify checksum since it is generated the same way as it is checked
                return data_gram
            else:
                raise DataNotRecognizedException(self.get_name(), cmd_byte)
        except SeatalkException as e:
            logger.error(repr(e) + " " + byte_to_str(cmd_byte) + byte_to_str(attribute) + bytes_to_str(data_bytes))
            raise
        finally:
            self._logger.write_raw_seatalk(cmd_byte, attribute, data_bytes, ingoing=True)
            await self._io_device.flush()
