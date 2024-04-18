import datetime

from abc import abstractmethod, ABCMeta

import logger
import device_io
import curio_wrapper
from common.helper import TimedCircleQueue
from shipdatabase import ShipDataBase


class Device(object, metaclass=ABCMeta):
    class RawDataLogger(logger.Logger):
        """
        Each device gets its own Logger which logs raw receive and sent data only
        """
        def __init__(self, device_name, terminator=""):
            super().__init__(log_file_name=device_name + "_raw.log", terminator=terminator, print_stdout=False)

        @staticmethod
        def _get_string(data, ingoing):
            sign = " <- " if ingoing else " -> "
            try:
                return sign + data
            except Exception as e:
                raise

        def info(self, data, ingoing=False):
            super().info(self._get_string(data, ingoing))

        def error(self, data, ingoing=False):
            super().error(self._get_string(data, ingoing))

        def warn(self, data, ingoing=False):
            super().warn(self._get_string(data, ingoing))

    def __init__(self, ship_data_base: ShipDataBase, name, io_device: device_io.IO, auto_flush: int = None, *args, **kwargs):
        """
        Initializes Device

        :param name: Name of device. For debugging purposes
        :param io_device: Instance if IO to receive data from
        :param auto_flush: Optional: Flushes IO after every x received datagram
        """
        self.ship_data_base = ship_data_base
        self._name = name
        self._io_device = io_device
        self._logger = self._get_data_logger()

        # Look in _check_flush(self) for more info
        self._auto_flush = auto_flush
        self._flush_idx = 0
        self._shutdown = False

    def _get_data_logger(self):
        return self.RawDataLogger(self._name)

    async def initialize(self):
        """
        Optional, if needed
        """
        logger.info(f"Initializing: {self.get_name()}")
        await self._io_device.initialize()

    @abstractmethod
    async def read_datagram(self):
        """
        Return last Datagram
        """
        raise NotImplementedError()

    @abstractmethod
    async def write_datagram(self, datagram):
        """
        Writes Datagram to Device (ot given IO)
        """
        raise NotImplementedError()

    def get_name(self) -> str:
        """
        Returns the name of the device
        """
        return self._name

    async def shutdown(self):
        """
        Stops given device
        """
        await self._io_device.cancel()
        self._shutdown = True

    def is_shutdown(self):
        """
        Getter for _shutdown
        :return: True if device is currently in shutdown
        """
        return self._shutdown

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

    @abstractmethod
    async def process_incoming_datagram(self):
        """
        Process read datagrams: put them into ship database
        """
        raise NotImplementedError()

    @abstractmethod
    async def process_outgoing_datagram(self):
        """
        Looks into ship database and try to extract and write datagrams from it
        """
        raise NotImplementedError()


class TaskDevice(Device, metaclass=ABCMeta):
    """
    Device implemented as "parallely" running tasks with buffered queues
    """
    def __init__(self, max_item_age_s=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        max_queue_size = 30

        if max_item_age_s is None:
            max_item_age_s = 30
        max_item_age_s = datetime.timedelta(seconds=max_item_age_s)

        if max_item_age_s.days == -1:
            max_item_age_s = 30
        self._write_queue = TimedCircleQueue(maxsize=max_queue_size, maxage=max_item_age_s)
        self._read_queue = TimedCircleQueue(maxsize=max_queue_size, maxage=max_item_age_s)
        self._write_task_handle = None
        self._read_task_handle = None

    async def initialize(self):
        """
        Starts tasks for transmitting and receiving messages
        """
        await super().initialize()
        self._write_task_handle = await curio_wrapper.TaskWatcher.daemon_spawn(self._write_to_io_task)
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
            datagram = await self._write_queue.get()
            await self._io_device.write(datagram)
            self._logger.info(datagram, ingoing=False)

    async def write_datagram(self, datagram):
        """
        Enqueues given Datagram to be written by IO
        """
        if self._write_queue.full():
            logger.warn(f"{self.get_name()}: Queue is full. Not writing")
        else:
            await self._write_queue.put(datagram)

    async def read_datagram(self):
        """
        Returns Datagram from queue
        """
        return await self._read_queue.get()

    async def shutdown(self):
        """
        Stops both task-handles (if spawned)
        """
        async with curio_wrapper.TaskGroupWrapper() as g:
            for task_handle in (self._write_task_handle, self._read_task_handle):
                if task_handle:
                    await g.spawn(task_handle.cancel)
