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
        self._port = int(port)


class TCPServer(TCP):
    amount_clients = 0

    def __init__(self, port):
        super().__init__(port)
        self._mtx = curio.Lock()
        self._read_queue = curio.Queue()

    async def initialize(self):
        await curio.spawn(curio.tcp_server(host='', port=self._port, client_connected_task=self._serve_client))

    async def _serve_client(self, client, address):
        logger.warn(f"Client {client} connected")
        if self.client:
            logger.error("Only one client allowed")
            await client.close()
            return
        try:
            self.__class__.amount_clients += 1
            self.client = client
            while True:
                data = await client.recv(100000)
                if not data:
                    break
                async with self._mtx:
                    for char_ in data.decode("UTF-8"):  # put every letter in it # TODO maybe ansii?
                        await self._read_queue.put(char_)
        except Exception:
            await client.close()
            raise
        finally:
            logger.warn(f"Client {address} closed connection")
            self.client = None
            self.__class__.amount_clients -= 1

    async def read(self, length=1):
        ret_val = ""
        for _ in range(length):
            ret_val += await self._read_queue.get()
        return ret_val

    async def write(self, data):
        if self.client:
            return await self.client.write(data)

    async def cancel(self):
        await self.client.close()

# TODO TCPClient(TCP):


class File(IO):
    def __init__(self, path):
        self._path_to_file = pathlib.Path(path)
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
        parity = self._get_parity_enum(parity)
        self._serial = serial.Serial(port=port, baudrate=baudrate, bytesize=bytesize, stopbits=stopbits, parity=parity)
        self._encoding = encoding

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

    async def write(self, data):
        if self._encoding:
            data = data.encode(encoding=self._encoding)

        return await curio.run_in_thread(partial(self._serial.write, data))

    async def read(self, length=1):
        return await curio.run_in_thread(partial(self._serial.read, length))

    async def cancel(self):
        self._serial.cancel_read()
        self._serial.cancel_write()
