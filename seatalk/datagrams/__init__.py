from .seatalk_datagram import SeatalkDatagram
from .s00_depth import Depth
from .s01_equipment_id import EquipmentID1
from .s10_apparent_wind_angle import ApparentWindAngle
from .s11_apparent_wind_speed import ApparentWindSpeed
from .s20_speed1 import Speed1
from .s21_trip_mileage import TripMileage
from .s22_total_mileage import TotalMileage
from .s23_water_temperature import WaterTemperature1
from .s24_display_units_mileage_speed import DisplayUnitsMileageSpeed
from .s25_TotalTripLog import TotalTripLog
from .s26_speed2 import Speed2
from .s27_water_temperature2 import WaterTemperature2
from .s30_set_lamp_intensity1 import SetLampIntensity1
from .s36_cancel_mob import CancelMOB
from .s38_code_lock_data import CodeLockData
from .s50_latitude_position import LatitudePosition
from .s51_longitude_position import LongitudePosition
from .s52_speed_over_ground import SpeedOverGround
from .s53_course_over_ground import CourseOverGround
from .s54_gmt_time import GMT_Time
from .s55_key_stroke1 import KeyStroke1
from .s56_date import Date
from .s57_sat_info import SatInfo
from .s58_position import Position
from .s59_countdown_timer import CountdownTimer
from .s60_e80_initialization import E80Initialization
from .s65_select_fathom import SelectFathom
from .s66_wind_alarm import WindAlarm
from .s68_alarm_acknowledgement import AlarmAcknowledgement
from .s6c_equipment_id import EquipmentID2
from .s6e_man_over_board import ManOverBoard
from .s80_set_lamp_intensity2 import SetLampIntensity2
from .s81_course_computer_setup import CourseComputerSetup
from .s82_target_waypoint_name import TargetWaypointName
from .s86_key_stroke2 import KeyStroke2
from .s87_set_response_level import SetResponseLevel
from .s90_device_identification1 import DeviceIdentification1
from .s91_set_rudder_gain import SetRudderGain
from .s93_enter_ap_setup import EnterAPSetup
from .s99_compass_variation import CompassVariation
from .sa4_device_identification2 import DeviceIdentification2

__all__ = ["Depth", "EquipmentID1", "ApparentWindAngle", "ApparentWindSpeed", "Speed1", "TripMileage", "TotalMileage",
           "WaterTemperature1", "DisplayUnitsMileageSpeed", "TotalTripLog", "Speed2", "WaterTemperature2",
           "SetLampIntensity1", "CancelMOB", "CodeLockData", "LatitudePosition", "LongitudePosition", "SpeedOverGround",
           "CourseOverGround", "GMT_Time", "KeyStroke1", "Date", "SatInfo", "Position", "CountdownTimer",
           "E80Initialization", "SelectFathom", "WindAlarm", "AlarmAcknowledgement", "EquipmentID2", "ManOverBoard",
           "SetLampIntensity2", "CourseComputerSetup", "TargetWaypointName", "KeyStroke2", "SetResponseLevel",
           "DeviceIdentification1", "SetRudderGain", "EnterAPSetup", "CompassVariation", "DeviceIdentification2",
           "SeatalkDatagram"]
