from device import TaskDevice
from nmea.nmea_datagram import NMEADatagram, NMEAParseError, UnknownDatagram, NMEAChecksumError
import logger


class NMEADevice(TaskDevice):
    async def _read_from_io_task(self):
        while True:
            data = await self._receive_datagram()
            log_function = self._logger.info
            try:
                NMEADatagram.verify_checksum(data)
                nmea_sentence = NMEADatagram.parse_nmea_sentence(data)
            except NMEAChecksumError as e:
                # If checksum does not match, ignore this message
                await self._io_device.flush()
                log_function = self._logger.error
                logger.error(f"Could not verify Checksum from {self.get_name()}: {repr(e)}")
                continue
            except NMEAParseError as e:
                # Every other non-checksum-exception: might be an internal computing-error, so ignore it
                nmea_sentence = UnknownDatagram(data)
                log_function = self._logger.warn
                logger.warn(f"Could not correctly parse message: {self.get_name()}: {repr(e)}")
            finally:
                log_function(data, ingoing=True)
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
                    self._logger.info(received, ingoing=True)
                    return received
        except TypeError as e:
            logger.error(f"{self.get_name()}: Error when reading. Wrong encoding?\n{repr(e)}")
            self._logger.error(received, ingoing=True)
            return ""
