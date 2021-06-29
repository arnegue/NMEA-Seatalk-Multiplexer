from device import TaskDevice
from nmea.nmea_datagram import NMEADatagram, NMEAParseError, UnknownDatagram, NMEAChecksumError
import logger


class NMEADevice(TaskDevice):
    async def _read_from_io_task(self):
        while True:
            data = await self._receive_datagram()
            try:
                NMEADatagram.verify_checksum(data)
                nmea_sentence = NMEADatagram.parse_nmea_sentence(data)
            except NMEAChecksumError as e:
                # If checksum does not match, ignore this message
                await self._io_device.flush()
                self._logger.error(data)
                logger.error(f"Could not read from {self.get_name()}: {repr(e)}")
                continue
            except NMEAParseError as e:
                # Every other non-checksum-exception: might be an internal computing-error, so ignore it
                nmea_sentence = UnknownDatagram(data)
                self._logger.warn(data)
                logger.warn(f"Could not correctly parse message: {self.get_name()}: {repr(e)}")
            else:
                self._logger.info(data)
            finally:
                await self._check_flush()
            await self._read_queue.put(nmea_sentence)

    async def _receive_datagram(self):
        received = ""

        try:
            # First receive start of nmea-message (either '$' or '!')
            received = ""
            while received != "$" and received != "!":
                received = await self._io_device.read(1)

            while 1:
                received += await self._io_device.read(1)
                if received[-1] == "\n":
                    self._logger.write_raw(received)
                    return received
        except TypeError as e:
            logger.error(f"{self.get_name()}: Error when reading. Wrong encoding?\n{repr(e)}")
            self._logger.error(received)
            return ""
