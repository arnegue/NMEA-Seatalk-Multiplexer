import inspect
from abc import ABCMeta

from common.helper import byte_to_str, bytes_to_str, get_numeric_byte_value
import logger
from common.parity_serial import ParityException
from device import TaskDevice
from device_io import SeatalkSerial
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
            datagram_bytes = bytearray()
            for value in rec, attribute, data:
                if isinstance(value, bytearray):
                    datagram_bytes += value
                else:
                    datagram_bytes.append(value)
            self.info(data=bytes_to_str(datagram_bytes), ingoing=ingoing)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._disable_parity = not isinstance(kwargs["io_device"], SeatalkSerial)
        self._last_read_parity_error = False   # See _receive_datagram
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
            datagram = bytearray()
            try:
                if self._disable_parity:
                    seatalk_datagram = await self._receive_seatalk_datagram_non_parity()
                else:
                    datagram = await self._receive_datagram()
                    seatalk_datagram = self.parse_datagram(datagram)
                if isinstance(seatalk_datagram, nmea_datagram.NMEADatagram):
                    await self._read_queue.put(seatalk_datagram)
                else:
                    raise NoCorrespondingNMEASentence(seatalk_datagram)
            except SeatalkException as e:
                logger.error(repr(e) + " " + bytes_to_str(datagram))
            finally:
                await self._check_flush()

    def parse_datagram(self, datagram: bytearray) -> SeatalkDatagram:
        cmd_byte = datagram[0]
        if len(datagram) < 3:  # 3 is minimum length of seatalk-message (command-byte, length byte, data byte)
            raise NotEnoughData(self, ">=3 bytes", len(datagram))
        elif cmd_byte not in self.__class__._seatalk_datagram_map:
            raise DataNotRecognizedException(self.get_name(), cmd_byte)

        # Extract datagram and instantiate
        seatalk_datagram = self.__class__._seatalk_datagram_map[cmd_byte]()

        # attribute byte tells how long the message will be and maybe some additional info important to the SeatalkDatagram
        attribute_nr = datagram[1]
        data_length = attribute_nr & 0x0F  # DataLength according to seatalk-datagram
        attr_data = (attribute_nr & 0xF0) >> 4
        # Verifies length (will raise exception before actually receiving data which won't be needed (should rarely happen)
        seatalk_datagram.verify_data_length(data_length)

        # At this point data_length is okay, finally receive it and progress whole datagram
        seatalk_datagram.process_datagram(first_half_byte=attr_data, data=datagram[2:])
        # No need to verify checksum since it is generated the same way as it is checked
        return seatalk_datagram

    async def _receive_datagram(self) -> bytearray:
        received_bytes = bytearray()

        # Receive until parity error occurs (or previous iteration had already a parity error. So avoid discard now-incoming datagram)
        # There might be more than one parity error
        cmd_byte = None
        attribute = bytearray()
        data_bytes = bytearray()
        while True:
            try:
                cmd_byte = await self._io_device.read(1)
            except ParityException:
                if cmd_byte is not None:
                    self._logger.write_raw_seatalk(cmd_byte, attribute, data_bytes, ingoing=True)
                cmd_byte = None
                self._last_read_parity_error = True
            if self._last_read_parity_error is True and cmd_byte is not None:
                break

        try:
            received_bytes += cmd_byte
            self._last_read_parity_error = False

            attribute_byte = await self._io_device.read(1)
            received_bytes += attribute_byte

            data_length = get_numeric_byte_value(attribute_byte) & 0x0F  # DataLength according to seatalk-datagram
            for i in range(data_length + 1):
                data_byte = await self._io_device.read(1)
                received_bytes += data_byte
                data_bytes += data_byte
            return received_bytes
        except ParityException as pe:
            self._last_read_parity_error = True
            raise SeatalkException(f"Unexpected ParityException when receiving datagram. Received bytes: {bytes_to_str(received_bytes)}") from pe
        finally:
            self._logger.write_raw_seatalk(cmd_byte, attribute, data_bytes, ingoing=True)

    async def _receive_seatalk_datagram_non_parity(self) -> SeatalkDatagram:
        """
        Legacy receiving: If parity check/generation is not possible use this function
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
