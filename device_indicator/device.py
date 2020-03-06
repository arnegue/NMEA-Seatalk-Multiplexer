import curio
from abc import abstractmethod
import threading
import pathlib
import serial
import logger
from device_indicator.nmea_datagram import NMEADatagram
from device_indicator.led_device_indicator import DeviceIndicator


class RawDataLogger(logger.Logger):
    def __init__(self, device_name):
        super().__init__(log_file_name=device_name + "_raw.log", log_format="%(asctime)s %(message)s", terminator="")

    def write_raw(self, data):
        # TODO encoded data?
        self.info(data)


class Device(object):
    def __init__(self, name):
        self._name = name
        self._device_indicator = None
        self._observers = []
        self._queue_size = 10
        self._write_queue = curio.UniversalQueue(maxsize=self._queue_size) # TODO what happens if queue is full? block-waiting, skipping, exception?
        self._read_queue = curio.UniversalQueue(maxsize=self._queue_size)
        self._logger = RawDataLogger(self._name)

    async def initialize(self):
        """
        Optional, if needed
        """
        pass

    @abstractmethod
    async def get_nmea_sentence(self):
        raise NotImplementedError()

    @abstractmethod
    async def write_to_device(self, sentence: NMEADatagram):
        raise NotImplementedError()

    def get_name(self):
        return self._name

    def set_observer(self, listener):
        self._observers.append(listener)

    def set_device_indicator(self, indicator: DeviceIndicator):
        self._device_indicator = indicator


class TCPDevice(Device):
    amount_clients = 0

    def __init__(self, port=40000):
        super().__init__(name=f"TCP-Server")

        self.client = None
        self._port = port

    async def initialize(self):
        await curio.tcp_server(host='', port=self._port, client_connected_task=self._serve_client)

    # TODO this could get weird with multiple connections

    async def _serve_client(self, client, address):
        logger.info(f"Incoming connection: {address} | Client {self.__class__.amount_clients}")
        self.__class__.amount_clients += 1
        self.client = client
        while True:
            data = await client.recv(100000)
            if not data:
                break
            self._logger.write_raw(data)
            await self._read_queue.put(data)
            # TODO write-queue

        logger.warn(f"Client {address} closed connection")
        self.client = None
        self.__class__.amount_clients -= 1

    async def get_nmea_sentence(self):
        return self._read_queue.get()

    async def write_to_device(self, sentence: NMEADatagram):
        await self._write_queue.put(sentence.get_nmea_sentence())


class FileDevice(Device):
    def __init__(self, path_to_file, name="FileDevice"):
        super().__init__(name=name)
        self._path_to_file = pathlib.Path(path_to_file)
        self._last_line = 0

    async def get_nmea_sentence(self):
        async with curio.aopen(self._path_to_file, "r") as file:
            lines = await file.readlines()
        if len(lines) <= self._last_line:
            self._last_line = 0
        ret_line = lines[self._last_line]
        self._last_line = self._last_line + 1 % len(lines)
        return ret_line

    async def write_to_device(self, sentence: NMEADatagram):
        async with curio.aopen(self._path_to_file, "a") as file:
            await file.write(sentence.get_nmea_sentence())

    async def initialize(self):
        if not self._path_to_file.exists():
            raise FileNotFoundError(f"File at path \"{str(self._path_to_file)}\" does not exist")


class SerialDevice(Device):
    class Stop(object):
        pass

    def __init__(self, name, port, max_queue_size=10, baudrate=4800, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE):
        super().__init__(name)
        self.port = port
        self._serial = serial.Serial(port=port, baudrate=baudrate, bytesize=bytesize, stopbits=stopbits, parity=parity)

        self._read_queue = curio.UniversalQueue(maxsize=max_queue_size)
        self._write_queue = curio.UniversalQueue(maxsize=max_queue_size)
        self._continue = True
        self._write_thread_handle = None
        self._read_thread_handle = None

    async def initialize(self):
        # TODO maybe a mutex is needed for read/write-thread when accessing serial?
        self._write_thread_handle = threading.Thread(target=self._write_thread)
        self._read_thread_handle = threading.Thread(target=self._read_thread)

        #self._write_thread_handle.start()
        self._read_thread_handle.start()

    @abstractmethod
    def _read_thread(self):
        pass

    def _write_thread(self):
        while self._continue:
            data = self._write_queue.get()
            if not isinstance(data, self.Stop):
                raw_data = data.encode(encoding='UTF-8')
                self._serial.write(raw_data)

    async def write_to_device(self, sentence: NMEADatagram):
        await self._write_queue.put(sentence.get_nmea_sentence())

    async def get_nmea_sentence(self):
        return await self._read_queue.get()

    async def shutdown(self):
        self._continue = False
        self._serial.cancel_read()
        self._serial.cancel_write()
        await self._write_queue.put(self.Stop())

        for thread in self._write_thread_handle, self._read_thread_handle:
            thread.join()


class NMEADevice(SerialDevice):
    def __init__(self, name, port, baudrate=4800):
        super().__init__(name, port, baudrate)

    def _read_thread(self):
        finished = False
        received = []
        while not finished:
            data = self._serial.read()
            received.append(data)
            if data == "\n":
                finished = True
        return received







