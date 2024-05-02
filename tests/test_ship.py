import time
from datetime import datetime

import curio
import pytest

from common.helper import PartPosition, Orientation, Position as HelperPosition
from nmea.nmea import NMEADevice
from nmea.nmea_datagram import RecommendedMinimumSentence, FAAModeIndicator, NMEAValidity
from seatalk.datagrams import Position as SeatalkPosition
from seatalk.seatalk import SeatalkDevice
from shipdatabase import ShipDataBase
from tests.test_nmea import TestNMEAIO
from tests.test_seatalk import TestSeatalkIO


class TestShip:
    def test_unset_data(self):
        ship = ShipDataBase()
        data = ship.speed_over_ground_knots
        assert data is None

    def test_not_existing_data(self):
        ship = ShipDataBase()
        with pytest.raises(AttributeError):
            _ = ship.abc

    @pytest.mark.skip("for now")
    def test_too_old_data(self):
        test_wait_time = 5
        ship = ShipDataBase(max_data_point_age_s=test_wait_time)
        ship.speed_over_ground_knots = 1  # Set Data

        time.sleep(test_wait_time - 2)  # This should work (1 < 5)
        data = ship.speed_over_ground_knots
        assert data == 1

        time.sleep(test_wait_time)  # This shouldn't work anymore, so None is returned
        data = ship.speed_over_ground_knots
        assert data is None

    test_position = HelperPosition(latitude=PartPosition(degrees=123, minutes=23.1, direction=Orientation.North),
                                   longitude=PartPosition(degrees=60, minutes=2.90, direction=Orientation.West))
    seatalk_position = SeatalkPosition(test_position)
    nmea_position = RecommendedMinimumSentence(datetime=datetime.now(),
                                               valid_status=NMEAValidity.Valid,
                                               position=test_position,
                                               speed_over_ground_knots=1.2,
                                               track_made_good=92,
                                               magnetic_variation=23,
                                               variation_sense=34,
                                               mode=FAAModeIndicator.Differential)

    @pytest.mark.curio
    async def test_seatalk_nmea(self):
        ship = ShipDataBase()

        # These two data aren't available via seatalk, so fake them that an RMC message can get generated
        ship.date = self.nmea_position.datetime
        ship.speed_over_ground_knots = self.nmea_position.speed_over_ground_knots

        seatalk_io = TestSeatalkIO(self.seatalk_position.get_seatalk_datagram())
        nmea_io = TestNMEAIO(None)
        seatalk_device = SeatalkDevice(name="SeatalkDevice", ship_data_base=ship, io_device=seatalk_io)
        nmea_device = NMEADevice(name="NMEADevice", ship_data_base=ship, io_device=nmea_io)
        await seatalk_device.initialize()
        await nmea_device.initialize()

        spawned_tasks = []
        for device_ in seatalk_device, nmea_device:
            spawned_tasks.append(await curio.spawn(device_.process_incoming_datagram))
            spawned_tasks.append(await curio.spawn(device_.process_outgoing_datagram))

        while 1:
            await curio.sleep(1)
            print(ship.longitude_position)
            print(ship.latitude_position)
            print(nmea_io.nmea_sentence)
            # TODO assert if position is set
            # TODO assert if nmea received it
            # nmea_io
        print(2)
        # Put seatalk_position into device
        # let time pass?
        # check if there is a nmea_position in output
        await seatalk_device.shutdown()
        await nmea_device.shutdown()
        for spawned_task in spawned_tasks:
            await spawned_task.join()

    @pytest.mark.curio
    async def test_nmea_seatalk(self):
        ship = ShipDataBase()
        seatalk_device = SeatalkDevice(name="SeatalkDevice", ship_data_base=ship, io_device=TestSeatalkIO(self.seatalk_position.get_seatalk_datagram()))  # TODO io_device?
        nmea_device = NMEADevice(name="NMEADevice", ship_data_base=ship, io_device=TestNMEAIO(self.nmea_position.get_nmea_sentence()))

        # Put nmea_device into device
        # let time pass?
        # check if there is a seatalk_device in output
