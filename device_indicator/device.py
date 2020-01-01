import curio

import logger
from device_indicator.led_device_indicator import DeviceIndicator


class NMEASentence(object):
    pass


class AsyncDevice(object):
    def __init__(self, name):
        self._name = name
        self._device_indicator = None
        self._observers = []

    async def initialize(self):
        """
        Optional, if needed
        """
        pass

    async def get_nmea_sentence(self):
        raise NotImplementedError()

    async def write_to_device(self, sentence: NMEASentence):
        raise NotImplementedError()

    def get_name(self):
        return self._name

    def set_observer(self, listener):
        self._observers.append(listener)

    def set_device_indicator(self, indicator: DeviceIndicator):
        self._device_indicator = indicator


class TCPDevice(AsyncDevice):
    client = 0

    def __init__(self, port=40000):
        super().__init__(name=f"TCP-Server-{self.__class__.client}")
        self.__class__.client += 1

        self.client = None
        self._port = port
        self._write_queue = curio.Queue()
        self._read_queue = curio.Queue()

    async def initialize(self):
        await curio.tcp_server(host='', port=self._port, client_connected_task=self._serve_client)

    async def _serve_client(self, client, address):
        logger.info(f"Incoming connection: {address}")
        self.client = client

        while True:
            data = await client.recv(100000)
            if not data:
                break
            await self._read_queue.put(data)

        logger.warn(f"Client {address} closed connection")
        await self.initialize()  # Reopen connection

    async def get_nmea_sentence(self):
        return self._read_queue.get()

    async def write_to_device(self, sentence: NMEASentence):
        await self._write_queue.put(sentence)


class SerialDevice(AsyncDevice):
    async def write_to_device(self):
        raise NotImplementedError()

    async def get_nmea_sentence(self):
        raise NotImplementedError()
