import curio
from abc import abstractmethod, ABCMeta
import logger
import device_io
import curio_wrapper
from nmea.nmea_datagram import NMEADatagram


class Device(object, metaclass=ABCMeta):
    class RawDataLogger(logger.Logger):
        """
        Each device gets it's own Logger which logs raw receive and sent data only
        """
        def __init__(self, device_name, terminator=""):
            super().__init__(log_file_name=device_name + "_raw.log", terminator=terminator, print_stdout=False)

        @staticmethod
        def _get_string(data, ingoing):
            sign = " <- " if ingoing else " -> "
            return sign + data

        def info(self, data, ingoing=False):
            super().info(self._get_string(data, ingoing))

        def error(self, data, ingoing=False):
            super().error(self._get_string(data, ingoing))

        def warn(self, data, ingoing=False):
            super().warn(self._get_string(data, ingoing))

    def __init__(self, name, io_device: device_io.IO, auto_flush: int = None):
        """
        Initializes Device

        :param name: Name of device. For debugging purposes
        :param io_device: Instance if IO to receive data from
        :param auto_flush: Optional: Flushes IO after every x received datagram
        """
        self._name = name
        self._io_device = io_device
        self._observers = set()
        self._logger = self._get_data_logger()

        # Look in _check_flush(self) for more info
        self._auto_flush = auto_flush
        self._flush_idx = 0

    def _get_data_logger(self):
        return self.RawDataLogger(self._name)

    async def initialize(self):
        """
        Optional, if needed
        """
        logger.info(f"Initializing: {self.get_name()}")
        await self._io_device.initialize()

    @abstractmethod
    async def get_nmea_datagram(self) -> NMEADatagram:
        """
        Return last NMEADatagram
        """
        raise NotImplementedError()

    @abstractmethod
    async def write_to_device(self, sentence: NMEADatagram):
        """
        Writes Datagram to Device (ot given IO)
        """
        raise NotImplementedError()

    def get_name(self) -> str:
        """
        Returns the name of the device
        """
        return self._name

    def get_observers(self) -> set:
        """
        Returns a set of observers for this device
        """
        return self._observers

    def set_observer(self, listener):
        """
        Adds an observer (instance of Device) to observer-list
        """
        self._observers.add(listener)

    async def shutdown(self):
        """
        Stops given device
        """
        await self._io_device.cancel()

    async def _check_flush(self):
        """
        If auto-flush is set: Increase index and check if it reached auto_flush. If is reached, flush io
        Warning: Only call this if flushing needs to be checked: Changes state of flush_index
        """
        if self._auto_flush:
            self._flush_idx += 1
            if self._flush_idx >= self._auto_flush:
                await self._io_device.flush()
                self._flush_idx = 0


class TaskDevice(Device, metaclass=ABCMeta):
    """
    Device implemented as "parallely" running tasks with buffered queues
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        max_queue_size = 10
        self._write_queue = curio.Queue(maxsize=max_queue_size)  # only nmea-datagrams
        self._read_queue = curio.Queue(maxsize=max_queue_size)   # only nmea-datagrams
        self._write_task_handle = None
        self._read_task_handle = None

    async def initialize(self):
        """
        Starts tasks for transmitting and receiving messages
        """
        await super().initialize()
        self._write_task_handle = await curio_wrapper.TaskWatcher.daemon_spawn(self._write_to_io_task)

        if len(self.get_observers()):  # If there are no observers, don't even bother to start read task
            self._read_task_handle = await curio_wrapper.TaskWatcher.daemon_spawn(self._read_from_io_task)

    @abstractmethod
    async def _read_from_io_task(self):
        """
        """
        raise NotImplementedError()

    async def _write_to_io_task(self):
        """
        Dequeues messages written from "write_to_device" and finally writes them to IO
        """
        while True:
            nmea_datagram = await self._write_queue.get()
            nmea_sentence = nmea_datagram.get_nmea_sentence()
            await self._io_device.write(nmea_sentence)
            self._logger.info(nmea_sentence, ingoing=False)

    async def write_to_device(self, nmea_datagram: NMEADatagram):
        """
        Enqueues given NMEADatagram to be written by IO
        """
        if self._write_queue.full():
            logger.warn(f"{self.get_name()}: Queue is full. Not writing")
        else:
            await self._write_queue.put(nmea_datagram)

    async def get_nmea_datagram(self):
        """
        Returns NMEADatagram from queue
        """
        return await self._read_queue.get()

    async def shutdown(self):
        """
        Stops both task-handles (if spawned)
        """
        async with curio_wrapper.TaskGroupWrapper() as g:
            for task_handle in (self._write_task_handle, self._read_task_handle):
                if task_handle:
                    await g.spawn(task_handle)
