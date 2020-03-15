from abc import abstractmethod, ABC
import pathlib
import curio
import serial
import logger
from functools import partial


class IO(object):
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
                logger.error(f"Could not decode: {data}")
                data = ""
        return data

    async def write(self, data):
        if self._encoding:
            try:
                data = data.encode(self._encoding)
            except UnicodeEncodeError:
                logger.error(f"Could not encode: {data}")
                data = bytes()

        async with self._read_write_lock:
            return await self._write(data)

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
    async def _read(self, length=1):
        await curio.sleep(1)
        return bytes([0])

    async def _write(self, data):
        data = data.decode(self._encoding)
        logger.info(data)


class TCP(IO, ABC):
    def __init__(self, port, encoding=False):
        super().__init__(encoding)
        self.client = None
        self._port = int(port)
        self._address = ""

        self._write_task_handle = None

        self._read_write_size = 100000
        self._read_queue = curio.Queue(self._read_write_size)
        self._write_queue = curio.Queue(self._read_write_size)

    async def _read(self, length=1):
        byte_array = bytearray()
        for _ in range(length):
            data = await self._read_queue.get()
            byte_array += data
        return byte_array

    async def _write(self, data):
        if not self.client:
            logger.info("TCP: Not writing, no client connected")
        if self._write_queue.full():
            logger.warn(f"TCP {self._address}:{self._port} Write-Queue is full. Not writing")
        else:
            await self._write_queue.put(data)

    async def cancel(self):
        await self.client.close()

    async def _write_task(self):
        while True:
            data = await self._write_queue.get()
            await self.client.sendall(data)

    async def _serve_client(self, client, address):
        self._address = address
        logger.info(f"Client {address[0]}:{address[1]} connected")
        if self.client:
            logger.error("Only one client allowed")
            await client.close()
            return

        self._write_task_handle = await curio.spawn(self._write_task)
        try:
            self.client = client
            while True:
                data_block = await client.recv(self._read_write_size)
                if not data_block:  # disconnected
                    break
                for data in data_block:  # put every letter in it
                    if self._read_queue.full():
                        logger.warn(f"TCP {self._address}:{self._port} Read-Queue is full. Not reading")
                    else:
                        await self._read_queue.put(data.to_bytes(1, "big"))
        except Exception:
            await client.close()
            raise
        finally:
            logger.warn(f"Client {address} closed connection")
            await self._write_task_handle.cancel()
            self.client = None
            self._address = ""


class TCPServer(TCP):
    async def initialize(self):
        await curio.spawn(curio.tcp_server(host='', port=self._port, client_connected_task=self._serve_client))


class TCPClient(TCP):
    def __init__(self, ip, port, encoding=False):
        super().__init__(port, encoding)
        self._ip = ip
        self._serve_client_task = None

    async def initialize(self):
        self._serve_client_task = await curio.spawn(self._open_connection)

    async def cancel(self):
        await super().cancel()
        await self._serve_client_task.cancel()

    async def _open_connection(self):
        while True:
            try:
                logger.info(f"Trying to connect to {self._ip}:{self._port}...")
                client = await curio.open_connection(self._ip, self._port)
                await self._serve_client(client, (self._ip, self._port))
            except (TimeoutError, ConnectionError) as e:
                logger.error("ConnectionError: " + repr(e))
                await curio.sleep(1)


class File(IO):
    def __init__(self, path, encoding):
        super().__init__(encoding)
        self._path_to_file = pathlib.Path(path)
        self._last_index = 0

    async def _read(self, length=1):
        async with curio.aopen(self._path_to_file, "rb") as file:
            lines = await file.read()
        # TODO no strings
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
    def __init__(self, port, baudrate=4800, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, encoding=None):
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

    async def cancel(self):
        self._serial.cancel_read()
        self._serial.cancel_write()
