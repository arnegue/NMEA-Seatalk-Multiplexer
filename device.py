import curio
from abc import abstractmethod, ABCMeta
import threading
import logger
import device_io
import curio_warpper
from nmea_datagram import NMEADatagram
from device_indicator.led_device_indicator import DeviceIndicator


class Device(object, metaclass=ABCMeta):
    class RawDataLogger(logger.Logger):
        def __init__(self, device_name):
            super().__init__(log_file_name=device_name + "_raw.log", log_format="%(asctime)s %(message)s", terminator="", print_stdout=False)

        def write_raw(self, data):
            self.info(data)

    def __init__(self, name, io_device: device_io.IO):
        self._name = name
        self._device_indicator = None
        self._io_device = io_device
        self._observers = []
        self._logger = self._get_data_logger()

    def _get_data_logger(self):
        return self.RawDataLogger(self._name)

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


class ThreadedDevice(Device, metaclass=ABCMeta):
    class Stop(object):
        pass

    def __init__(self, name, io_device, max_queue_size=10):
        super().__init__(name, io_device)
        self._write_queue = curio.UniversalQueue(maxsize=max_queue_size)  # TODO what happens if queue is full? block-waiting, skipping, exception?
        self._read_queue = curio.UniversalQueue(maxsize=max_queue_size)
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
        while True:
            data = self._write_queue.get()
            if not isinstance(data, self.Stop):
                self._io_device.write(data)

    async def write_to_device(self, sentence: NMEADatagram):
        await self._write_queue.put(sentence.get_nmea_sentence())

    async def get_nmea_sentence(self):
        return await self._read_queue.get()

    async def shutdown(self):
        await self._write_queue.put(self.Stop())

        for thread in self._write_thread_handle, self._read_thread_handle:
            thread.join()


class TaskDevice(Device, metaclass=ABCMeta):
    def __init__(self, name, io_device, max_queue_size=10):
        super().__init__(name, io_device)
        self._write_queue = curio.Queue(maxsize=max_queue_size)   # TODO what happens if queue is full? block-waiting, skipping, exception?
        self._read_queue = curio.Queue(maxsize=max_queue_size)
        self._write_task_handle = None
        self._read_task_handle = None

    async def initialize(self):
        await super().initialize()
        self._write_task_handle = await curio.spawn(self._write_task)
        self._read_task_handle = await curio.spawn(self._read_task)  # threading.Thread(target=self._read_thread)

    @abstractmethod
    async def _read_task(self):
        pass

    async def _write_task(self):
        while True:
            data = await self._write_queue.get()
            await self._io_device.write(data)

    async def write_to_device(self, sentence: NMEADatagram):
        await self._write_queue.put(sentence.get_nmea_sentence())

    async def get_nmea_sentence(self):
        return await self._read_queue.get()

    async def shutdown(self):
        async with curio_warpper.TaskGroupWrapper() as g:
            await g.spawn(self._write_task_handle.cancel)
            await g.spawn(self._read_task_handle.cancel)

