import curio
import logger
import json
import argparse
import inspect

import curio_wrapper
import device
from nmea import nmea
import device_io
import special_devices
from seatalk import seatalk


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
        content = await file.read()
    content = json.loads(content)

    device_classes_dict = create_devices_dict()
    device_instance_dict = {}
    for name in content:
        device_dict = content[name]
        device_type = device_classes_dict[device_dict["type"]]
        auto_flush = device_dict.get("auto_flush", None)

        device_io_dict = device_dict["device_io"]
        device_io_type = device_io_dict.pop("type")
        device_io_class = getattr(device_io, device_io_type)

        # Passes named parameters to to-be-created-objects (even None)
        # if parameter is not given, default value will be assumed
        device_io_instance = device_io_class(**{k: v for k, v in device_io_dict.items() if (v is not None)})
        device_instance = device_type(name=name, io_device=device_io_instance, auto_flush=auto_flush)
        logger.info(f"Instantiated Device {name} of type: {device_type.__name__}, IO {device_io_class.__name__}")
        device_instance_dict[name] = device_instance

    for observable in device_instance_dict.values():
        observable_name = observable.get_name()
        observable_instance = device_instance_dict[observable_name]
        for observer in content[observable_name]["observers"]:
            observer_instance = device_instance_dict[observer]
            observable_instance.set_observer(observer_instance)

    return device_instance_dict.values()


async def device_receiver_task(device_):
    await curio.sleep(0)
    observers = device_.get_observers()
    if len(observers):
        logger.info(f"Device {device_.get_name()} has observers")
        while not device_.is_shutdown():
            try:
                logger.debug(f"Trying to get NMEA-Sentence from {device_.get_name()}....")
                sentence = await device_.get_nmea_datagram()
                logger.info(f"Received {sentence.__class__.__name__}")
            except curio.TaskTimeout:
                logger.debug(f"Timeout reading from {device_.get_name()}")  # Wont work sometimes
                continue
            async with curio_wrapper.TaskGroupWrapper() as g:
                for observer in observers:
                    if observer.is_shutdown():
                        logger.debug(f"Observer {observer.get_name()} was shutdown. Unsubscribung")
                        device_.unset_observer(observer)
                        break  # need to break since set changed size
                    else:
                        logger.debug(f"Writing to device: {observer.get_name()}")
                        await g.spawn(observer.write_to_device, sentence)
            await curio.sleep(0)
        logger.info(f"Stopped reiving. Device {device_.get_name()} got shutdown")
    else:
        logger.info(f"Device {device_.get_name()} doesn't have observers")


async def main(devices_path):
    list_devices = await create_devices(devices_path)
    logger.info("Starting...")

    async with curio_wrapper.TaskGroupWrapper() as g:
        for device_ in list_devices:
            await g.spawn(device_.initialize)

    # Spawn for every listening device a observer task
    async with curio_wrapper.TaskGroupWrapper() as g:
        for device_ in list_devices:
            await g.spawn(device_receiver_task, device_)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NMEA-Seatalk-Multiplexer.')
    parser.add_argument('--devices', default="devices.json", help='Path to json-file containing needed information for creating devices')

    args = parser.parse_args()
    curio.run(main, args.devices)
