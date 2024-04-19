import inspect
from abc import ABCMeta

from common.helper import byte_to_str, bytes_to_str
import logger
from common.parity_serial import ParityException
from device import TaskDevice
from nmea import nmea_datagram
import seatalk
from seatalk.datagrams.seatalk_datagram import SeatalkDatagram
from seatalk.seatalk_exceptions import SeatalkException, DataNotRecognizedException, NotEnoughData, NoCorrespondingNMEASentence


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
            self.__class__._seatalk_datagram_map = self.get_datagram_map()

    @staticmethod
    def get_datagram_map():
        """
        Return every datagram-class there is with it's seatalk_id (cmd_byte) as key
        """
        return_dict = {}
        for name, obj in inspect.getmembers(seatalk):
            # Abstract, non-private SeatalkDatagrams
            if inspect.isclass(obj) and issubclass(obj, SeatalkDatagram) and not inspect.isabstract(obj) and obj.__name__[0] != '_':
                return_dict[obj.seatalk_id] = obj

        return return_dict

    def _get_data_logger(self):
        return self.RawSeatalkLogger(self._name)

    async def _read_from_io_task(self):
        """
        For more info: http://www.thomasknauf.de/seatalk.htm
        """
        while True:
            data_gram = await self._receive_datagram()
            try:
                cmd_byte = data_gram[0]
                if len(data_gram) >= 3:  # 3 is minimum length of seatalk-message (command-byte, length byte, data byte)
                    if cmd_byte in self.__class__._seatalk_datagram_map:
                        # Extract datagram and instantiate
                        seatalk_datagram = self.__class__._seatalk_datagram_map[cmd_byte]()

                        # attribute byte tells how long the message will be and maybe some additional info important to the SeatalkDatagram
                        attribute_nr = data_gram[1]
                        data_length = attribute_nr & 0x0F  # DataLength according to seatalk-datagram
                        attr_data = (attribute_nr & 0xF0) >> 4
                        # Verifies length (will raise exception before actually receiving data which won't be needed
                        seatalk_datagram.verify_data_length(data_length)

                        # At this point data_length is okay, finally receive it and progress whole datagram
                        seatalk_datagram.process_datagram(first_half_byte=attr_data, data=data_gram[2:])
                        # No need to verify checksum since it is generated the same way as it is checked

                        if isinstance(seatalk_datagram, nmea_datagram.NMEADatagram):
                            await self._read_queue.put(seatalk_datagram)
                        else:
                            raise NoCorrespondingNMEASentence(seatalk_datagram)
                    else:
                        raise DataNotRecognizedException(self.get_name(), cmd_byte)
                else:
                    raise NotEnoughData(self, ">=3 bytes", len(data_gram))
            except SeatalkException as e:
                logger.error(repr(e) + " " + byte_to_str(data_gram))
            finally:
                await self._check_flush()

    async def _receive_datagram(self):
        received_bytes = bytearray()
        # Receive until parity error occurs
        while True:
            try:
                received_byte = await self._io_device.read(1)
            except ParityException:
                if len(received_bytes) > 0:
                    break
            else:
                received_bytes += received_byte
        return received_bytes
