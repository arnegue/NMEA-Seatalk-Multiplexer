import curio
from abc import abstractmethod
import threading
import logger
import device_io
from nmea_datagram import NMEADatagram
from device_indicator.led_device_indicator import DeviceIndicator


class Device(object):
    class RawDataLogger(logger.Logger):
        def __init__(self, device_name):
            super().__init__(log_file_name=device_name + "_raw.log", log_format="%(asctime)s %(message)s", terminator="")

        def write_raw(self, data):
            # TODO encoded data?
            self.info(data)

    def __init__(self, name, io_device: device_io.IO):
        self._name = name
        self._device_indicator = None
        self._io_device = io_device
        self._observers = []
        self._queue_size = 10
        self._logger = self.RawDataLogger(self._name)

    async def initialize(self):
        """
        Optional, if needed
        """
        await self._io_device.initialize()

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

    async def shutdown(self):
        await self._io_device.cancel()


class ThreadedDevice(Device):
    class Stop(object):
        pass

    def __init__(self, name, io_device, max_queue_size=10):
        super().__init__(name, io_device)
        self._write_queue = curio.UniversalQueue(maxsize=self._queue_size)  # TODO what happens if queue is full? block-waiting, skipping, exception?
        self._read_queue = curio.UniversalQueue(maxsize=self._queue_size)
        self._read_queue = curio.UniversalQueue(maxsize=max_queue_size)
        self._write_queue = curio.UniversalQueue(maxsize=max_queue_size)
        self._continue = True
        self._write_thread_handle = None
        self._read_thread_handle = None

    async def initialize(self):
        self._write_thread_handle = threading.Thread(target=self._write_thread)
        self._read_thread_handle = threading.Thread(target=self._read_thread)

        self._write_thread_handle.start()
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
        await self._write_queue.put(self.Stop())

        for thread in self._write_thread_handle, self._read_thread_handle:
            thread.join()









