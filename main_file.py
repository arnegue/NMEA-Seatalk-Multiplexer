import curio
import logger
import json
import argparse

import curio_wrapper
import device
import nmea
import device_io
import inspect
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


def create_devices_dict():
    devices_dict = {}
    for module in device, seatalk, nmea:
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, device.Device):
                devices_dict[name] = obj
    return devices_dict


async def create_devices(path):
    # Read JSon-File
    async with curio.aopen(path) as file:
        content = await file.read()
    content = json.loads(content)
    #list_devices = []

    device_classes_dict = create_devices_dict()
    device_instance_dict = {}
    for name in content:
        device_dict = content[name]
        device_type = device_classes_dict[device_dict['type']]

        device_io_dict = device_dict["device_io"]
        device_io_type = device_io_dict.pop("type")
        device_io_class = getattr(device_io, device_io_type)

        device_io_instance = device_io_class(**{k: v for k, v in device_io_dict.items() if (v is not None)})
        device_instance = device_type(name=name, io_device=device_io_instance)
        device_instance_dict[name] = device_instance

    for observable in device_instance_dict.values():
        observable_name = observable.get_name()
        observable_instance = device_instance_dict[observable_name]
        for observer in content[observable_name]["observers"]:
            observer_instance = device_instance_dict[observer]
            observable_instance.set_observer(observer_instance)

    return device_instance_dict.values()


async def main(devices_path):
    list_devices = await create_devices(devices_path)
    logger.info("Starting...")

    async with curio_wrapper.TaskGroupWrapper() as g:
        for device_ in list_devices:
            await g.spawn(device_.initialize)

    while 1:
        for device_ in list_devices:
            observers = device_.get_observers()
            if len(observers):
                try:
                    #async with curio.timeout_after(1):
                    sentence = await device_.get_nmea_sentence()
                except curio.TaskTimeout:
                    logger.warn(f"Timeout reading from {device_.get_name()}")
                    continue
                for observer in device_.get_observers():
                    async with curio_wrapper.TaskGroupWrapper() as g:
                        await g.spawn(observer.write_to_device, sentence)
                await curio.sleep(3)
            else:
                logger.info(f"Device {device_.get_name()} does not have any observers")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NMEA-Seatalk-Multiplexer.')
    parser.add_argument('--devices', default="devices.json",
                        help='Path to json-file containing needed information for creating devices')

    args = parser.parse_args()
    curio.run(main, args.devices)

