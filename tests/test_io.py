import pytest
import os

import curio_wrapper
from device_io import *


test_tcp_port = 9991
 

class TestFileClass(File):
    async def initialize(self):
        """
        Create empty file
        """
        async with curio.aopen(self._path_to_file, "w") as file:
            await file.write("")
        await super().initialize()

    async def cancel(self):
        """
        Deletes test-file
        """
        os.remove(self._path_to_file)
        await super().cancel()


async def get_clients_server_fixture(amount_clients=2):
    """
    Returns two clients connected to a server
    """
    encoding = "UTF-8"

    server = TCPServer(port=test_tcp_port, encoding=encoding)
    await server.initialize()

    clients = [TCPClient(ip="localhost", port=test_tcp_port, encoding=encoding) for _ in range(amount_clients)]
    for client in clients:
        await client.initialize()

    async with curio.timeout_after(10):  # Shouldn't take that long
        while len(server.clients) != len(clients):
            await curio.sleep(0.5)  # Wait for clients to connect

    return clients, server


@pytest.mark.curio
@pytest.mark.parametrize(("tested_instance", "counter_part_instance"), (
                         (TCPServer(port=test_tcp_port),                 TCPClient(ip="localhost", port=test_tcp_port)),
                         (TCPClient(ip="localhost", port=test_tcp_port), TCPServer(port=test_tcp_port)),
                         (TestFileClass("logs/test_file.bin"),           File("logs/test_file.bin")),
                         (Serial(port="COM2"),                           Serial(port="COM3"))
                         ))
async def test_io_binary_none_binary(tested_instance, counter_part_instance):
    """
    Tests simple read-write to/from given IO
    """
    tested_instance.encoding = False
    counter_part_instance.encoding = False
    binary_data = bytearray([0x00, 0x01, 0x02, 0x03, 0x04])
    try:
        await tested_instance.initialize()
        await counter_part_instance.initialize()

        async with curio.timeout_after(5):
            while await tested_instance.write(binary_data) != len(binary_data):
                await curio.sleep(0.5)

        received = await counter_part_instance.read(len(binary_data))

        assert received == binary_data

        await counter_part_instance.write(binary_data)
        received = await tested_instance.read(len(binary_data))

        assert received == binary_data
    finally:
        await tested_instance.cancel()
        await counter_part_instance.cancel()


@pytest.mark.curio
async def test_multiple_clients_write():
    """
    Tests to write to multiple clients, checks if received data is the same as sent
    """
    clients, server = await get_clients_server_fixture()

    client_1_data = "Hello"
    client_2_data = "World"

    read_task = await curio.spawn(server.read(len(client_1_data + client_2_data)))

    async with curio_wrapper.TaskGroupWrapper() as g:
        await g.spawn(clients[0].write, client_1_data)
        await g.spawn(clients[1].write, client_2_data)

    read_task_result = await read_task.join()

    if read_task_result not in ((client_1_data + client_2_data), (client_2_data + client_1_data)):
        raise AssertionError(f"ReadResult wrong: {read_task_result}")
    for client in clients:
        await client.cancel()
    await server.cancel()


@pytest.mark.curio
@pytest.mark.parametrize("direction", (True, False))
async def test_client_reconnect(direction):
    """
    Tests for client and server to disconnect and reconnect

    True -> client disconnects
    False -> server disconnects
    """
    clients, server = await get_clients_server_fixture(1)
    client = clients[0]

    aborter, stayer = (client, server) if direction else (server, client)

    await aborter.cancel()
    while len(stayer.clients) > 0:
        await curio.sleep(0.5)

    await aborter.initialize()

    while len(stayer.clients) < 0:
        await curio.sleep(0.5)

    await aborter.cancel()
    await stayer.cancel()


@pytest.mark.curio
async def test_client_abort():
    """
    Tries to open a 1-to-1 server-client pair, de-initializes it and to initialize them again. Target is that only one connection is build up
    """
    for i in range(2):
        amount_clients = 1
        clients, server = await get_clients_server_fixture(amount_clients)
        assert len(clients) == len(server.clients) == amount_clients
        await server.cancel()
        await clients[0].cancel()
    print("Success")


@pytest.mark.curio
async def test_multiple_clients_read():
    """
    Tests multiple clients if both read the same sent data
    """
    clients, server = await get_clients_server_fixture()

    server_data = "Hello" + "World"

    read_tasks = [await curio.spawn(client.read(len(server_data))) for client in clients]

    await server.write(server_data)

    read_task_results = [await read_task.join() for read_task in read_tasks]

    for read_task_result in read_task_results:
        assert read_task_result == server_data

    await server.cancel()
    for client in clients:
        await client.cancel()
    print("finished")


@pytest.mark.curio
async def test_write2_after_client1_closed():
    """
    Tests if server still writes to 2nd client if 1st client closed connection
    """
    clients, server = await get_clients_server_fixture()

    server_data = "Hello" + "World"

    # Write and read to all clients
    read_tasks = [await curio.spawn(client.read(len(server_data))) for client in clients]
    await server.write(server_data)
    read_task_results = [await read_task.join() for read_task in read_tasks]
    for read_task_result in read_task_results:
        assert read_task_result == server_data

    # Abort first connection
    await clients[0].cancel()
    # Wait for server to notice it
    while len(server.clients) < 1:
        await curio.sleep(0.5)

    # Write again
    await server.write(server_data)
    read_data = await clients[1].read(len(server_data))
    assert read_data == server_data

    await server.cancel()
    await clients[1].cancel()


