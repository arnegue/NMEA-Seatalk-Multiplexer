from device import TaskDevice


class NMEADevice(TaskDevice):
    def __init__(self, name, io_device):
        super().__init__(name=name, io_device=io_device)

    async def _read_task(self):
        while True:
            data = await self._receive_until_new_line()
            await self._read_queue.put(data)

    async def _receive_until_new_line(self):
        received = []
        while 1:
            data = await self._io_device.read()
            received.append(data)
            if data == "\n":
                return received
