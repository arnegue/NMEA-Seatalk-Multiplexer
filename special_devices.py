from device import Device
from common import helper
from nmea.nmea_datagram import NMEADatagram, RecommendedMinimumSentence, NMEAValidity


class SpecialDeviceException(Exception):
    """
    Exception concerning special devices
    """


class SetTimeDevice(Device):
    """
    Receives RMC-Sentences until one contains a valid date, then shuts down
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._time_set = False  # TODO better kind of unsubscribing

    async def get_nmea_datagram(self) -> NMEADatagram:
        raise SpecialDeviceException(f"No receiving from {self.get_name()}")

    async def write_to_device(self, sentence: NMEADatagram):
        if not self._time_set:
            if isinstance(sentence, RecommendedMinimumSentence) and sentence.valid_status == NMEAValidity.Valid:
                self._logger.info(f"Setting date {sentence.date} from {sentence.get_nmea_sentence()}")
                helper.set_system_time(sentence.date)
                self._time_set = True
                await self.shutdown()
