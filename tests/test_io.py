import device_io
import pytest
import curio
import curio_wrapper


async def get_clients_server():
    port = 9999
    encoding = "UTF-8"
    amount_clients = 2

    server = device_io.TCPServer(port=port, encoding=encoding)
    await server.initialize()

    clients = [device_io.TCPClient(ip="localhost", port=port, encoding=encoding) for _ in range(amount_clients)]
    for client in clients:
        await client.initialize()

    while len(server.clients) != len(clients):
        await curio.sleep(0.5)  # Wait for clients to connect

    return clients, server


@pytest.mark.curio
async def test_multiple_clients_write():
    clients, server = await get_clients_server()

    client_1_data = "Hello"
    client_2_data = "World"

    read_task = await curio.spawn(server.read(len(client_1_data + client_2_data)))

    async with curio_wrapper.TaskGroupWrapper() as g:
        await g.spawn(clients[0].write, client_1_data)
        await g.spawn(clients[1].write, client_2_data)

    read_task_result = await read_task.join()

    if read_task_result not in ((client_1_data + client_2_data), (client_2_data + client_1_data)):
        raise AssertionError(f"ReadResult wrong: {read_task_result}")


@pytest.mark.curio
async def test_multiple_clients_read():
    clients, server = await get_clients_server()

    server_data = "Hello" + "World"

    read_tasks = [await curio.spawn(client.read(len(server_data))) for client in clients]

    await server.write(server_data)

    read_task_results = [await read_task.join() for read_task in read_tasks]

    for read_task_result in read_task_results:
        assert read_task_result == server_data
