import inspect
from abc import ABCMeta

import curio

from common.helper import get_numeric_byte_value, byte_to_str, bytes_to_str, UnitConverter, Position as HelperPosition
import logger
from device import TaskDevice
import seatalk.datagrams  # For get_datagram_map
from seatalk.datagrams import *  # For handling ship-database
from seatalk.seatalk_exceptions import SeatalkException, DataNotRecognizedException


class SeatalkDevice(TaskDevice, metaclass=ABCMeta):
    _seatalk_datagram_map = dict()

    class RawSeatalkLogger(TaskDevice.RawDataLogger):
        def __init__(self, device_name):
            super().__init__(device_name=device_name, terminator="\n")

        def info(self, data, ingoing=False):
            if isinstance(data, str):
                super().info(data, ingoing)
            else:
                data_gram_bytes = bytearray()
                for value in data:
                    if isinstance(value, bytearray):
                        data_gram_bytes += value
                    else:
                        data_gram_bytes.append(value)
                super().info(data=bytes_to_str(data_gram_bytes), ingoing=ingoing)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_own_datagrams = set()  # Set of own datagrams (avoid sending back own messages)

        # Initially fill datagram-map with every datagram-class there is with it's seatalk_id (cmd_byte) as key
        if len(self.__class__._seatalk_datagram_map) == 0:
            self.__class__._seatalk_datagram_map = self.get_datagram_map()

    @staticmethod
    def get_datagram_map():
        """
        Return every datagram-class there is with it's seatalk_id (cmd_byte) as key
        """
        return_dict = {}
        for name, obj in inspect.getmembers(seatalk.datagrams):
            # Abstract, non-private SeatalkDatagrams
            if inspect.isclass(obj) and issubclass(obj, SeatalkDatagram) and not inspect.isabstract(obj) and obj.__name__[0] != '_':
                return_dict[obj.seatalk_id] = obj

        return return_dict

    def _get_data_logger(self):
        return self.RawSeatalkLogger(self._name)

    async def _read_from_io_task(self):
        while True:
            try:
                data_gram = await self.receive_datagram()
                logger.info(f"Received: {data_gram.__class__.__name__}")
                await self._read_queue.put(data_gram)
            except SeatalkException:
                pass
            finally:
                await self._check_flush()

    async def receive_datagram(self):
        """
        For more info: http://www.thomasknauf.de/seatalk.htm
        """
        cmd_byte = int()
        attribute = bytearray()
        data_bytes = bytearray()
        try:
            # Get Command-Byte
            cmd_byte = get_numeric_byte_value(await self._io_device.read(1))

            self._set_own_datagrams.add(cmd_byte)

            if cmd_byte in self.__class__._seatalk_datagram_map:
                # Extract datagram and instantiate it
                data_gram = self.__class__._seatalk_datagram_map[cmd_byte]()

                # Receive attribute byte which tells how long the message will be and maybe some additional info important to the SeatalkDatagram
                attribute = await self._io_device.read(1)
                attribute_nr = get_numeric_byte_value(attribute)
                data_length = attribute_nr & 0x0F  # DataLength according to seatalk-datagram. length of 0 means 1 byte of data
                attr_data = (attribute_nr & 0xF0) >> 4
                # Verifies length (will raise exception before actually receiving data which won't be needed
                data_gram.verify_data_length(data_length)

                # At this point data_length is okay, finally receive it and progress whole datagram
                data_bytes += await self._io_device.read(data_length + 1)
                data_gram.process_datagram(first_half_byte=attr_data, data=data_bytes)
                # No need to verify checksum since it is generated the same way as it is checked
                return data_gram
            else:
                raise DataNotRecognizedException(self.get_name(), cmd_byte)  # TODO Put this into queue too (if it's valid)
        except SeatalkException as e:
            logger.error(repr(e) + " " + byte_to_str(cmd_byte) + byte_to_str(attribute) + bytes_to_str(data_bytes))
            raise
        finally:
            self._logger.info([cmd_byte, attribute, data_bytes], ingoing=True)
            await self._io_device.flush()

    async def process_incoming_datagram(self):
        while not self.is_shutdown():
            datagram = await self.read_datagram()
            if isinstance(datagram, Depth):
                self.ship_data_base.depth_m = UnitConverter.feet_to_meter(datagram.depth_feet)
                # TODO anchor-alarm etc?
            elif isinstance(datagram, ApparentWindAngle):
                self.ship_data_base.apparent_wind_angle = datagram.angle_degree
            elif isinstance(datagram, ApparentWindSpeed):
                self.ship_data_base.apparent_wind_speed_knots = datagram.speed_knots
            elif isinstance(datagram, Speed1):
                self.ship_data_base.speed_through_water_knots = datagram.speed_knots
            elif isinstance(datagram, TripMileage):
                self.ship_data_base.trip_mileage_miles = datagram.mileage_miles
            elif isinstance(datagram, TotalMileage):
                self.ship_data_base.total_mileage_miles = datagram.mileage_miles
            elif isinstance(datagram, WaterTemperature1):
                if not datagram.sensor_defective:
                    self.ship_data_base.water_temperature_c = datagram.temperature_c
            elif isinstance(datagram, TotalTripLog):
                self.ship_data_base.trip_mileage_miles = datagram.total_miles  # TODO correct?
            elif isinstance(datagram, Speed2):
                self.ship_data_base.speed_through_water_knots = datagram.speed_knots
            elif isinstance(datagram, WaterTemperature2):
                self.ship_data_base.water_temperature_c = datagram.temperature_c
            elif isinstance(datagram, SetLampIntensity1):
                self.ship_data_base.set_light_intensity = datagram.set_key
            elif isinstance(datagram, LatitudePosition):
                self.ship_data_base.latitude_position = datagram.position
            elif isinstance(datagram, LongitudePosition):
                self.ship_data_base.longitude_position = datagram.position
            elif isinstance(datagram, SpeedOverGround):
                self.ship_data_base.speed_over_ground_knots = datagram.speed_knots
            elif isinstance(datagram, CourseOverGround):
                self.ship_data_base.course_over_ground_degree_magnetic = datagram.course_degrees
            elif isinstance(datagram, GMT_Time):
                self.ship_data_base.time = datagram.time
            elif isinstance(datagram, Date):
                self.ship_data_base.date = datagram.date
            elif isinstance(datagram, Position):
                self.ship_data_base.latitude_position = datagram.position.latitude
                self.ship_data_base.longitude_position = datagram.position.longitude
            elif isinstance(datagram, SetLampIntensity2):
                self.ship_data_base.set_light_intensity = datagram.set_key
            elif isinstance(datagram, TargetWaypointName):
                if self.ship_data_base.target_waypoints is None:
                    self.ship_data_base.target_waypoints = []
                if datagram.name not in self.ship_data_base.target_waypoints:
                    self.ship_data_base.target_waypoints.append((datagram.name, None))  # None -> No position

    async def process_outgoing_datagram(self):
        while not self.is_shutdown():
            send_datagrams = []
            if self.ship_data_base.depth_m is not None:
                send_datagrams.append(Depth(depth_feet=self.ship_data_base.depth_m))  # TODO set every bit to 0
            if self.ship_data_base.apparent_wind_angle is not None:
                send_datagrams.append(ApparentWindAngle(angle_degree=self.ship_data_base.apparent_wind_angle))
            if self.ship_data_base.apparent_wind_speed_knots is not None:
                send_datagrams.append(ApparentWindSpeed(speed_knots=self.ship_data_base.apparent_wind_speed_knots))
            if self.ship_data_base.speed_through_water_knots is not None:
                send_datagrams.append(Speed1(speed_knots=self.ship_data_base.speed_through_water_knots))
                send_datagrams.append(Speed2(speed_knots=self.ship_data_base.speed_through_water_knots))
            if self.ship_data_base.trip_mileage_miles is not None:
                send_datagrams.append(TripMileage(mileage_miles=self.ship_data_base.trip_mileage_miles))
                send_datagrams.append(TotalMileage(mileage_miles=self.ship_data_base.trip_mileage_miles))
            if self.ship_data_base.water_temperature_c is not None:
                send_datagrams.append(WaterTemperature1(temperature_c=self.ship_data_base.water_temperature_c, sensor_defective=0))
                send_datagrams.append(WaterTemperature2(temperature_c=self.ship_data_base.water_temperature_c))
            if self.ship_data_base.set_light_intensity is not None:
                send_datagrams.append(SetLampIntensity1(intensity=self.ship_data_base.set_light_intensity))
                send_datagrams.append(SetLampIntensity2(intensity=self.ship_data_base.set_light_intensity))
            if self.ship_data_base.latitude_position is not None:
                send_datagrams.append(LatitudePosition(position=self.ship_data_base.latitude_position))
            if self.ship_data_base.longitude_position is not None:
                send_datagrams.append(LongitudePosition(position=self.ship_data_base.longitude_position))
            if self.ship_data_base.speed_over_ground_knots is not None:
                send_datagrams.append(SpeedOverGround(speed_knots=self.ship_data_base.speed_over_ground_knots))
            if self.ship_data_base.course_over_ground_degree_magnetic is not None:
                send_datagrams.append(CourseOverGround(course_degrees=self.ship_data_base.course_over_ground_degree_magnetic))
            if self.ship_data_base.utc_time is not None:
                send_datagrams.append(GMT_Time(time=self.ship_data_base.time))
            if self.ship_data_base.date is not None:
                send_datagrams.append(Date(date=self.ship_data_base.date))
            if self.ship_data_base.latitude_position is not None and self.ship_data_base.longitude_position is not None:
                send_datagrams.append(Position(HelperPosition(latitude=self.ship_data_base.latitude_position,
                                                              longitude=self.ship_data_base.longitude_position)))
            if self.ship_data_base.target_waypoints is not None:
                for waypoint_name, way_point_pos in self.ship_data_base.target_waypoints:
                    send_datagrams.append(TargetWaypointName(waypoint_name))

            for datagram in send_datagrams:
                if datagram.seatalk_id not in self._set_own_datagrams:
                    await self.write_datagram(datagram.get_seatalk_datagram())
            await curio.sleep(0.5)
