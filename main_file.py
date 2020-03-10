import curio
import logger
import json
import serial

import curio_warpper
import device
import device_io
import seatalk
TCP_PIN_R = 14
TCP_PIN_G = 7
TCP_PIN_B = 6

# USB0 Radio
# USB1 GPS
# USB2 Wind
# USB3 Seatalk


async def test_file():
    file = device_io.File("logs/example_gps_dump.log")
    for i in range(3):
        r = await file.read(2)
        print(r)


async def test_serial():
    serial = device_io.Serial("COM2")
    for i in range(5):
        r = await serial.read(2)
        print(r)


async def create_devices(path="devices.json"):
    # Read JSon-File
    async with curio.aopen(path) as file:
        content = await file.read()
    content = json.loads(content)
    list_devices = []

    # Iterate thorugh dict
    for name in content:
        device_dict = content[name]
        device_type = getattr(device, device_dict['type'], None)
        if not device_type:
            device_type = getattr(seatalk, device_dict['type'], None)

        device_io_dict = device_dict["device_io"]
        device_io_type = device_io_dict.pop("type")
        device_io_class = getattr(device_io, device_io_type)

        device_io_instance = device_io_class(**{k: v for k, v in device_io_dict.items() if (v is not None)})
        device_instance = device_type(name=name, io_device=device_io_instance)
        list_devices.append(device_instance)
    return list_devices


async def main():
    list_devices = await create_devices()
    logger.info("Starting...")

    # intensity_diagram.get_set_intensity()
    #st = seatalk.SeatalkDevice("Seatalk", port="COM10")
    #st = device.FileDevice("./logs/example_gps_dump.log")
    async with curio_warpper.TaskGroupWrapper() as g:
        for device in list_devices:
            await g.spawn(device.initialize)

    last_intensity = 0
    while 1:
        print(f"intensity: {last_intensity}")
        data = intensity_diagram.get_set_intensity(last_intensity)
        last_intensity = (last_intensity + 1) % 3
        await st._write_queue.put(data)
        await curio.sleep(2)


curio.run(main)