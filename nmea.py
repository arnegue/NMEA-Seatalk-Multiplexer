from device import ThreadedDevice


class NMEADevice(ThreadedDevice):
    def __init__(self, name, io_device):
        super().__init__(name=name, io_device=io_device)

    def _read_thread(self):
        while self._continue:
            data = self._receive_until_new_line()
            self._read_queue.put(data)

    async def _receive_until_new_line(self):
        received = []
        while 1:
            data = await self._io_device.read()
            received.append(data)
            if data == "\n":
                return received
