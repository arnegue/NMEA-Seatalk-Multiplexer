from datetime import datetime

from device import Device
from common import helper


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

    async def read_datagram(self):
        pass  # "Nothing to do"

    async def write_datagram(self, datagram):
        pass  # "Nothing to do"

    async def process_incoming_datagram(self):
        pass  # "Nothing to do"

    async def process_outgoing_datagram(self):
        """
        Once a valid RMC was received, shutdown
        """
        if self.ship_data_base.date is not None and self.ship_data_base.utc_time is not None:
            dt_combined = datetime.combine(self.ship_data_base.date, self.ship_data_base.utc_time)
            helper.set_system_time(dt_combined)
            await self.shutdown()
