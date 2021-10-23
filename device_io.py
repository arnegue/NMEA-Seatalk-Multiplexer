from abc import abstractmethod, ABC
import pathlib
import curio
import serial
import logger
from functools import partial

from curio_wrapper import TaskGroupWrapper


class IO(object):
    """
    Base IO class, providing read and write methods
    """
    def __init__(self, encoding=False):
        self._encoding = encoding
        self._read_write_lock = curio.Lock()

    async def read(self, length=1):
        async with self._read_write_lock:
            data = await self._read(length)
        if self._encoding:
            try:
                data = data.decode(self._encoding)
            except UnicodeDecodeError:
                logger.error(f"{type(self).__name__}: Could not decode: {data}")
                data = ""
        else:
            data = bytearray(data)
        return data

    async def write(self, data):
        if self._encoding:
            try:
                data = data.encode(self._encoding)
            except UnicodeEncodeError:
                logger.error(f"{type(self).__name__}: Could not encode: {data}")
                data = bytearray()

        async with self._read_write_lock:
            return await self._write(data)

    async def flush(self):
        pass

    @abstractmethod
    async def _read(self, length=1):
        pass

    @abstractmethod
    async def _write(self, data):
        pass

    async def initialize(self):
        pass

    async def cancel(self):
        pass


class StdOutPrinter(IO):
    """
    IO-Class for StdOut
    """
    async def _read(self, length=1):
        await curio.sleep(0)
        return bytearray([0])

    async def _write(self, data):
        data = data.decode(self._encoding)
        logger.info(f"{type(self).__name__}: {data}")
        await curio.sleep(0)
        return len(data)


class TCP(IO, ABC):
    """
    Basic Abstract Class for TCP-Connections
    """
    def __init__(self, port, encoding=False):
        super().__init__(encoding)
        self.clients = []
        self._port = int(port)
        self._address = ""

        self._write_task_handle = None

        self._read_write_size = 1000
        self._init_queues()
        self._temp_read_block = None

    def _init_queues(self):
        self._read_queue = curio.Queue(self._read_write_size)
        self._write_queue = curio.Queue(self._read_write_size)

    async def _read(self, length=1):
        byte_array = bytearray()
        for _ in range(length):
            if self._temp_read_block is None or len(self._temp_read_block) == 0:
                self._temp_read_block = await self._read_queue.get()

            data = self._temp_read_block[:1]
            self._temp_read_block = self._temp_read_block[1:]
            byte_array += data
        return byte_array

    async def _write(self, data):
        if not self.clients:
            logger.info(f"{type(self).__name__}: Not writing, no client connected")
            return 0
        if self._write_queue.full():
            logger.warn(f"{type(self).__name__}: {self._address}:{self._port} Write-Queue is full. Not writing")
            return 0
        else:
            await self._write_queue.put(data)
            return len(data)

    async def cancel(self):
        await self._write_task_handle.cancel()
        async with TaskGroupWrapper() as g:
            for client in self.clients:
                await g.spawn(client.close)

    async def _write_task(self):
        while True:
            data = await self._write_queue.get()
            for client in self.clients:
                async with TaskGroupWrapper() as g:
                    await g.spawn(client.sendall, data)

    async def _serve_client(self, client, address):
        self._address = address
        logger.info(f"{type(self).__name__}: Client {address[0]}:{address[1]} connected")

        try:
            self.clients.append(client)
            while True:
                data_block = await client.recv(self._read_write_size)
                if not data_block:  # disconnected
                    break
                if self._read_queue.full():
                    logger.warn(f"TCP {self._address}:{self._port} Read-Queue is full. Not reading")
                else:
                    await self._read_queue.put(data_block)
        finally:
            await client.close()
            logger.info(f"{type(self).__name__}: Client {address[0]}:{address[1]} disconnected")
            self.clients.remove(client)
            self._address = ""
            raise ConnectionError("Close connection")

    async def flush(self):
        self._init_queues()

    async def initialize(self):
        self._write_task_handle = await curio.spawn(self._write_task)


class TCPServer(TCP):
    """
    TCP-Server Class
    """
    def __init__(self, port, encoding=False):
        super().__init__(port, encoding)
        self.server_task = None

    async def initialize(self):
        await super().initialize()
        self.server_task = await curio.spawn(curio.tcp_server(host='', port=self._port, client_connected_task=self._serve_client))

    async def cancel(self):
        await self.server_task.cancel()

        async with curio.timeout_after(10):
            while len(self.clients) > 0:
                await curio.sleep(0.5)
        await super().cancel()


class TCPClient(TCP):
    """
    TCP-Client-Class
    """
    def __init__(self, ip, port, encoding=False):
        super().__init__(port, encoding)
        self._ip = ip
        self._serve_client_task = None
        self._close = False

    async def initialize(self):
        await super().initialize()
        self._serve_client_task = await curio.spawn(self._open_connection)

    async def cancel(self):
        self._close = True
        await self._serve_client_task.cancel()
        await super().cancel()

    async def _open_connection(self):
        while True:
            try:
                logger.info(f"{type(self).__name__}: Trying to connect to {self._ip}:{self._port}...")
                connection = await curio.open_connection(self._ip, self._port)
                await self._serve_client(connection, (self._ip, self._port))
            except (TimeoutError, ConnectionError, OSError) as e:
                # Reconnect if theses errors occur
                logger.exception(F"{type(self).__name__}: Exception:", e)
                if self._close:
                    raise
                await curio.sleep(5)


class File(IO):
    """
    Class for reading and writing to file
    """
    def __init__(self, path, encoding=False):
        super().__init__(encoding)
        self._path_to_file = pathlib.Path(path)
        self._last_index = 0

    async def _read(self, length=1):
        async with curio.aopen(self._path_to_file, "rb") as file:
            lines = await file.read()
        ret_val = lines[self._last_index:(self._last_index + length)]
        self._last_index += length
        if ret_val == "":
            await curio.sleep(0)
        return ret_val

    async def _write(self, data):
        async with curio.aopen(self._path_to_file, "ab") as file:
            return await file.write(data)

    async def initialize(self):
        if not self._path_to_file.exists():
            raise FileNotFoundError(f"File at path \"{str(self._path_to_file)}\" does not exist")


class Serial(IO):
    """
    IO-Class providing methods to read and write from/to serial periphery
    """
    def __init__(self, port, baudrate=4800, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, encoding=False):
        super().__init__(encoding)
        parity = self._get_parity_enum(parity)
        self._serial = serial.Serial(port=port, baudrate=baudrate, bytesize=bytesize, stopbits=stopbits, parity=parity)

    @staticmethod
    def _get_parity_enum(parity):
        """
        Some wrapper necessary to get that enum. Could also get just the first letter but that doesnt look good
        """
        if isinstance(parity, str) and len(parity) > 1:
            for val in serial.PARITY_NAMES:
                if serial.PARITY_NAMES[val] == parity:
                    return val
        return parity

    async def _write(self, data):
        return await curio.run_in_thread(partial(self._serial.write, data))

    async def _read(self, length=1):
        return await curio.run_in_thread(partial(self._serial.read, length))

    async def flush(self):
        self._serial.flush()
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

    async def cancel(self):
        self._serial.cancel_read()
        self._serial.cancel_write()
