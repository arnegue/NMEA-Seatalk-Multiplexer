import curio
from abc import abstractmethod, ABCMeta
import logger
import device_io
import curio_wrapper
from nmea_datagram import NMEADatagram, NMEAParseError
from device_indicator.led_device_indicator import DeviceIndicator


class Device(object, metaclass=ABCMeta):
    class RawDataLogger(logger.Logger):
        def __init__(self, device_name, terminator=""):
            super().__init__(log_file_name=device_name + "_raw.log", terminator=terminator, print_stdout=False)

        def write_raw(self, data):
            self.info(data)

    def __init__(self, name, io_device: device_io.IO):
        self._name = name
        self._device_indicator = None
        self._io_device = io_device
        self._observers = set()
        self._logger = self._get_data_logger()

    def _get_data_logger(self):
        return self.RawDataLogger(self._name)

    async def initialize(self):
        """
        Optional, if needed
        """
        logger.info(f"Initializing: {self.get_name()}")
        await self._io_device.initialize()

    @abstractmethod
    async def get_nmea_sentence(self):
        raise NotImplementedError()

    @abstractmethod
    async def write_to_device(self, sentence: NMEADatagram):
        raise NotImplementedError()

    def get_name(self):
        return self._name

    def get_observers(self):
        return self._observers

    def set_observer(self, listener):
        self._observers.add(listener)

    def set_device_indicator(self, indicator: DeviceIndicator):
        self._device_indicator = indicator

    async def shutdown(self):
        await self._io_device.cancel()


class TaskDevice(Device, metaclass=ABCMeta):
    def __init__(self, name, io_device, max_queue_size=10):
        super().__init__(name, io_device)
        self._write_queue = curio.Queue(maxsize=max_queue_size)  # only nmea-datagrams
        self._read_queue = curio.Queue(maxsize=max_queue_size)  # only nmea-datagrams
        self._write_task_handle = None
        self._read_task_handle = None

    async def initialize(self):
        await super().initialize()
        self._write_task_handle = await curio.spawn(self._write_task)

        if len(self.get_observers()):  # If there are no observers, don't even bother to start read task
            self._read_task_handle = await curio.spawn(self._read_task)

    @abstractmethod
    async def _read_task(self):
        pass

    async def _write_task(self):
        while True:
            data = await self._write_queue.get()
            try:
                NMEADatagram.verify_checksum(data)
                await self._io_device.write(data)
            except NMEAParseError as e:  # TODO maybe already do it when write_to_device is called
                logger.error(f"Will not write to {self.get_name()}: {repr(e)}")

    async def write_to_device(self, sentence: NMEADatagram):
        if self._write_queue.full():
            logger.warn(f"{self.get_name()}: Queue is full. Not writing")
        else:
            if isinstance(sentence, NMEADatagram):
                sentence = sentence.get_nmea_sentence()
            await self._write_queue.put(sentence)

    async def get_nmea_sentence(self):
        return await self._read_queue.get()

    async def shutdown(self):
        async with curio_wrapper.TaskGroupWrapper() as g:
            await g.spawn(self._write_task_handle.cancel)
            await g.spawn(self._read_task_handle.cancel)

