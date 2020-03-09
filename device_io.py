from abc import abstractmethod, ABC
import pathlib
import curio
import serial
import logger
from functools import partial


class IO(object):
    # TODO maybe a mutex is needed for read/write-thread when accessing?
    @abstractmethod
    async def read(self, length=1):
        pass

    @abstractmethod
    async def write(self, data):
        pass

    async def initialize(self):
        pass

    async def cancel(self):
        pass


class TCP(IO, ABC):
    def __init__(self, port):
        self.client = None
        self._port = port


class TCPServer(TCP):
    amount_clients = 0

    def __init__(self, port):
        super().__init__(port)
        self._last_index = 0
        self._read_str = ""

    async def initialize(self):
        await curio.tcp_server(host='', port=self._port, client_connected_task=self._serve_client)

    async def _serve_client(self, client, address):
        if self.client:
            logger.error("Only one client allowed")
            await client.close()
            return

        self.__class__.amount_clients += 1
        self.client = client
        while True:
            data = await client.recv(100000)
            if not data:
                break
            self._read_str += str(data)

        logger.warn(f"Client {address} closed connection")
        self.client = None
        self.__class__.amount_clients -= 1

    async def read(self, length=1):
        ret_val = self._read_str[self._last_index:(self._last_index + length)]
        self._last_index += length
        self._read_str = self._read_str[self._last_index:]  # Remove read bytes from buffer
        return ret_val

    async def write(self, data):
        if self.client:
            return await self.client.write(data)

    async def cancel(self):
        await self.client.close()

# TODO TCPClient(TCP):


class File(IO):
    def __init__(self, path_to_file):
        self._path_to_file = pathlib.Path(path_to_file)
        self._last_index = 0

    async def read(self, length=1):
        async with curio.aopen(self._path_to_file, "r") as file:
            lines = await file.read()

        ret_val = lines[self._last_index:(self._last_index + length)]
        self._last_index += length
        return ret_val

    async def write(self, data):
        async with curio.aopen(self._path_to_file, "a") as file:
            return await file.write(data)

    async def initialize(self):
        if not self._path_to_file.exists():
            raise FileNotFoundError(f"File at path \"{str(self._path_to_file)}\" does not exist")


class Serial(IO):
    def __init__(self, port, baudrate=4800, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, encoding='UTF-8'):
        self._serial = serial.Serial(port=port, baudrate=baudrate, bytesize=bytesize, stopbits=stopbits, parity=parity)
        self._encoding = encoding

    async def write(self, data):
        if self._encoding:
            data = data.encode(encoding=self._encoding)

        return await curio.run_in_thread(partial(self._serial.write, data))

    async def read(self, length=1):
        return await curio.run_in_thread(partial(self._serial.read, length))

    async def cancel(self):
        self._serial.cancel_read()
        self._serial.cancel_write()
