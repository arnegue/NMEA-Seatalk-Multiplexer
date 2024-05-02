import curio
import json
import argparse
import inspect

import curio_wrapper
import logger
import device
from nmea import nmea
import device_io
import special_devices
from seatalk import seatalk
from shipdatabase import ShipDataBase


def create_devices_dict():
    """
    Creates a list of classes which may be instantiated if given in given devices-json-list
    """
    devices_dict = {}
    for module in device, seatalk, nmea, special_devices:
        for name, obj in inspect.getmembers(module):
            if inspect.isclass(obj) and issubclass(obj, device.Device):
                devices_dict[name] = obj
    return devices_dict


async def create_devices(path):
    """
    Creates devices-instances and its io-devices from given path to json-file
    """
    # Read JSon-File
    async with curio.aopen(path) as file:
        file_content = await file.read()
    file_content = json.loads(file_content)

    device_classes_dict = create_devices_dict()
    device_instance_dict = {}
    ship_db = ShipDataBase()
    for name, device_dict in file_content.items():
        try:
            device_type = device_classes_dict[device_dict["type"]]
            if "auto_flush" not in device_dict:
                device_dict["auto_flush"] = None

            max_item_age_s = device_dict["max_item_age_s"] if "max_item_age_s" in device_dict else None
            device_dict["max_item_age_s"] = max_item_age_s
            device_dict["ship_data_base"] = ship_db

            device_io_dict = device_dict["device_io"]
            device_io_type = device_io_dict.pop("type")
            device_io_class = getattr(device_io, device_io_type)

            # Passes named parameters to to-be-created-objects (even None)
            # if parameter is not given, default value will be assumed
            device_io_instance = device_io_class(**{k: v for k, v in device_io_dict.items() if v is not None})
            device_instance = device_type(**device_dict, name=name, io_device=device_io_instance)
            logger.info(f"Instantiated Device {name} of type: {device_type.__name__}, IO {device_io_class.__name__}")
            device_instance_dict[name] = device_instance
        except Exception:
            logger.error(f"Error in configuration of device {name}")
            raise

    return device_instance_dict.values()


async def main(devices_path):
    list_devices = await create_devices(devices_path)
    logger.info("Starting...")

    async with curio_wrapper.TaskGroupWrapper() as g:
        for device_ in list_devices:
            await g.spawn(device_.initialize)

    async with curio_wrapper.TaskGroupWrapper() as g:
        for device_ in list_devices:
            await g.spawn(device_.process_incoming_datagram)
            await g.spawn(device_.process_outgoing_datagram)


if __name__ == '__main__':
    logger.GeneralLogger()  # Instantiate logger once
    parser = argparse.ArgumentParser(description='NMEA-Seatalk-Multiplexer.')
    parser.add_argument('--devices', default="devices.json", help='Path to json-file containing needed information for creating devices')

    args = parser.parse_args()
    curio.run(main, args.devices)
