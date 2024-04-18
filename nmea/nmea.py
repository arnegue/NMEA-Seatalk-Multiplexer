import curio

from common.helper import Position
from device import TaskDevice
from nmea.nmea_datagram import NMEADatagram, NMEAParseError, UnknownDatagram, NMEAChecksumError, \
    RecommendedMinimumSentence, TrackMadeGoodGroundSpeed, GPSDOPActiveSatellites, DepthBelowKeel, SpeedThroughWater, \
    WaterTemperature, WindSpeedAndAngle, GPSModes, NMEAValidity
import logger


class NMEADevice(TaskDevice):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_own_datagrams = set()  # Set of own datagrams (avoid sending back own messages)

    async def _read_from_io_task(self):
        while True:
            data = await self._receive_datagram()
            log_function = self._logger.info
            try:
                NMEADatagram.verify_checksum(data)
                nmea_sentence = NMEADatagram.parse_nmea_sentence(data)
            except NMEAChecksumError as e:
                # If checksum does not match, ignore this message
                await self._io_device.flush()
                log_function = self._logger.error
                logger.error(f"Could not verify Checksum from {self.get_name()}: {repr(e)}")
                continue
            except NMEAParseError as e:
                # Every other non-checksum-exception: might be an internal computing-error, so ignore it
                nmea_sentence = UnknownDatagram(data)
                log_function = self._logger.warn
                logger.warn(f"Could not correctly parse message: {self.get_name()}: {repr(e)}")
            finally:
                log_function(data, ingoing=True)
                await self._check_flush()

            self._set_own_datagrams.add(nmea_sentence.nmea_tag)
            await self._read_queue.put(nmea_sentence)

    async def _receive_datagram(self):
        """
        Receives whole NMEA-Sentence (from $ or ! to \n)

        :return: whole sentence as string
        """
        received = ""

        try:
            # First receive start of nmea-message (either '$' or '!')
            received = ""
            while received != "$" and received != "!":
                received = await self._io_device.read(1)

            while True:
                received += await self._io_device.read(1)
                if received[-1] == "\n":
                    return received
        except TypeError as e:
            logger.exception(f"{self.get_name()}: Error when reading. Wrong encoding?", e)
            self._logger.error(received, ingoing=True)
            return ""

    async def process_incoming_datagram(self):
        while not self.is_shutdown():
            datagram = await self.read_datagram()
            if isinstance(datagram, RecommendedMinimumSentence):
                self.ship_data_base.date = datagram.datetime.date()
                self.ship_data_base.utc_time = datagram.datetime.time()
                self.ship_data_base.latitude_position = datagram.position.latitude
                self.ship_data_base.longitude_position = datagram.position.longitude
                self.ship_data_base.speed_over_ground_knots = datagram.speed_over_ground_knots
                # TODO track_made_good? Doesnt that depend on a WayPoint?
                # TODO Magnetic variation?
                # TODO variation_sense
                # TODO mode
            elif isinstance(datagram, TrackMadeGoodGroundSpeed):
                self.ship_data_base.speed_over_ground_knots = datagram.speed_over_ground_knots
                self.ship_data_base.course_over_ground_degree_true = datagram.course_over_ground_degree_true
                self.ship_data_base.course_over_ground_degree_magnetic = datagram.course_over_ground_degree_magnetic
            elif isinstance(datagram, GPSDOPActiveSatellites):
                pass
            elif isinstance(datagram, DepthBelowKeel):
                self.ship_data_base.depth_m = datagram.depth_m
            elif isinstance(datagram, SpeedThroughWater):
                self.ship_data_base.speed_through_water_knots = datagram.speed_knots
                self.ship_data_base.heading_degrees_magnetic = datagram.heading_degrees_magnetic
                self.ship_data_base.heading_degrees_true = datagram.heading_degrees_true
            elif isinstance(datagram, WaterTemperature):
                self.ship_data_base.water_temperature_c = datagram.temperature_c
            elif isinstance(datagram, WindSpeedAndAngle):
                if datagram.reference_true:
                    self.ship_data_base.true_wind_speed_knots = datagram.speed_knots
                    self.ship_data_base.true_wind_speed_angle = datagram.angle_degree
                else:
                    self.ship_data_base.apparent_wind_speed_knots = datagram.speed_knots
                    self.ship_data_base.apparent_wind_angle = datagram.angle_degree
                # TODO valid_status
            else:
                # At this point we do are not able to put data directly into ship-data-base,
                # instead just put it in the list
                self.ship_data_base._list_unknown_nmea_datagrams.append(datagram)

    async def process_outgoing_datagram(self):
        send_datagrams = []
        # TODO maybe dont even create diagram if its in _set_own_datagrams
        if (self.ship_data_base.date is not None and  # Date: what if only DMY is set, but not HMS (or vise versa)
                self.ship_data_base.latitude_position is not None and
                self.ship_data_base.longitude_position is not None and
                self.ship_data_base.speed_over_ground_knots is not None):  # TODO check other members too
            send_datagrams.append(RecommendedMinimumSentence(datetime=self.ship_data_base.date,
                                                             valid_status=NMEAValidity.Valid,
                                                             position=Position(latitude=self.ship_data_base.latitude_position,
                                                                               longitude=self.ship_data_base.longitude_position),
                                                             speed_over_ground_knots=self.ship_data_base.speed_over_ground_knots,
                                                             track_made_good=0,  # TODO
                                                             magnetic_variation=0,  # TODO
                                                             variation_sense=0,  # TODO
                                                             ))

        if (self.ship_data_base.speed_over_ground_knots is not None and
                self.ship_data_base.course_over_ground_degree_true is not None and
                self.ship_data_base.course_over_ground_degree_magnetic is not None):
            send_datagrams.append(TrackMadeGoodGroundSpeed(course_over_ground_degree_true=self.ship_data_base.course_over_ground_degree_true,
                                                           course_over_ground_degree_magnetic=self.ship_data_base.course_over_ground_degree_magnetic,
                                                           speed_over_ground_knots=self.ship_data_base.speed_over_ground_knots,
                                                           mode=GPSModes.Automatic))
        # TODO GPSDOPActiveSatellites
        if self.ship_data_base.depth_m is not None:
            send_datagrams.append(DepthBelowKeel(depth_m=self.ship_data_base.depth_m))

        if (self.ship_data_base.speed_through_water_knots is not None and
                self.ship_data_base.heading_degrees_magnetic is not None and
                self.ship_data_base.heading_degrees_true is not None):
            send_datagrams.append(SpeedThroughWater(speed_knots=self.ship_data_base.speed_through_water_knots,
                                                    heading_degrees_true=self.ship_data_base.heading_degrees_true,
                                                    heading_degrees_magnetic=self.ship_data_base.heading_degrees_magnetic))

        if self.ship_data_base.water_temperature_c is not None:
            send_datagrams.append(WaterTemperature(temperature_c=self.ship_data_base.water_temperature_c))

        if (self.ship_data_base.true_wind_speed_knots is not None and
                self.ship_data_base.true_wind_speed_angle is not None):
            send_datagrams.append(WindSpeedAndAngle(angle_degree=self.ship_data_base.true_wind_speed_angle,
                                                    reference_true=True,
                                                    speed_knots=self.ship_data_base.true_wind_speed_knots,
                                                    validity=NMEAValidity.Valid))
        if (self.ship_data_base.apparent_wind_speed_knots is not None and
                self.ship_data_base.apparent_wind_angle is not None):  # TODO if or elif?
            send_datagrams.append(WindSpeedAndAngle(angle_degree=self.ship_data_base.apparent_wind_angle,
                                                    reference_true=False,
                                                    speed_knots=self.ship_data_base.apparent_wind_speed_knots,
                                                    validity=NMEAValidity.Valid))
        for datagram in send_datagrams:
            if datagram.nmea_tag not in self._set_own_datagrams:
                await self.write_datagram(datagram.get_nmea_sentence())
        await curio.sleep(0.5)
