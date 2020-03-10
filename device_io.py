from abc import abstractmethod, ABC
import pathlib
import curio
import serial
import logger
from functools import partial


class IO(object):
    def __init__(self, encoding):
        self._encoding = encoding

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


class StdOutPrinter(IO):
    async def read(self, length=1):
        await curio.sleep(0)
        return ""

    async def write(self, data):
        await curio.sleep(0)
        logger.info(data)


class TCP(IO, ABC):
    amount_clients = 0

    def __init__(self, port, encoding):
        super().__init__(encoding)
        self.client = None
        self._port = int(port)

        self._read_queue = curio.Queue()

    async def read(self, length=1):
        ret_val = ""
        for _ in range(length):
            ret_val += await self._read_queue.get()
        return ret_val

    async def write(self, data):
        if self.client:
            return await self.client.sendall(data.encode(self._encoding))

    async def cancel(self):
        await self.client.close()

    async def _serve_client(self, client, address):
        logger.info(f"Client {client} connected")
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
                for char_ in data.decode(self._encoding):  # put every letter in it # TODO maybe ansii?
                    await self._read_queue.put(char_)
        except Exception:
            await client.close()
            raise
        finally:
            logger.warn(f"Client {address} closed connection")
            self.client = None
            self.__class__.amount_clients -= 1


class TCPServer(TCP):
    async def initialize(self):
        await curio.spawn(curio.tcp_server(host='', port=self._port, client_connected_task=self._serve_client))


class TCPClient(TCP):
    def __init__(self, ip, port, encoding):
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
                await self._serve_client(client, self._ip)
            except ConnectionError as e:
                logger.error("ConnectionError: " + repr(e))
                await curio.sleep(1)


class File(IO):
    def __init__(self, path, encoding):
        super().__init__(encoding)
        self._path_to_file = pathlib.Path(path)
        self._last_index = 0

    async def read(self, length=1):
        async with curio.aopen(self._path_to_file, "r") as file:
            lines = await file.read()

        ret_val = lines[self._last_index:(self._last_index + length)]
        self._last_index += length
        if ret_val == "":
            await curio.sleep(0)
        return ret_val

    async def write(self, data):
        async with curio.aopen(self._path_to_file, "a") as file:
            return await file.write(data)

    async def initialize(self):
        if not self._path_to_file.exists():
            raise FileNotFoundError(f"File at path \"{str(self._path_to_file)}\" does not exist")


class Serial(IO):
    def __init__(self, port, baudrate=4800, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE, encoding='ASCII'):
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

    async def write(self, data):
        if self._encoding:
            data = data.encode(encoding=self._encoding)

        return await curio.run_in_thread(partial(self._serial.write, data))

    async def read(self, length=1):
        return await curio.run_in_thread(partial(self._serial.read, length))

    async def cancel(self):
        self._serial.cancel_read()
        self._serial.cancel_write()
