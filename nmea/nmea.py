from device import TaskDevice
from nmea.nmea_datagram import NMEADatagram, NMEAParseError, UnknownNMEATag, UnknownDatagram
import logger


class NMEADevice(TaskDevice):
    def __init__(self, name, io_device):
        super().__init__(name=name, io_device=io_device)

    async def _read_from_io_task(self):
        while True:
            data = await self._receive_until_new_line()
            try:
                NMEADatagram.verify_checksum(data)
                try:
                    nmea_sentence = NMEADatagram.parse_nmea_sentence(data)
                except UnknownNMEATag:
                    nmea_sentence = UnknownDatagram(data)  # Not that bad if the tag is unknown
                self._logger.info(data)
                await self._read_queue.put(nmea_sentence)
            except NMEAParseError as e:
                await self._io_device.flush()
                self._logger.error(data)
                logger.error(f"Could not read from {self.get_name()}: {repr(e)}")
                continue

    async def _receive_until_new_line(self):
        received = ""
        while 1:
            try:
                data = await self._io_device.read()
                received += data
                if data == "\n":
                    self._logger.write_raw(received)
                    return received
            except TypeError as e:
                logger.error(f"{self.get_name()}: Error when reading. Wrong encoding?\n{repr(e)}")
                self._logger.error(received)
                return ""
