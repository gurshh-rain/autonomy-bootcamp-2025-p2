"""
Decision-making logic.
"""

import math

from pymavlink import mavutil

from ..common.modules.logger import logger
from ..telemetry import telemetry


class Position:
    """
    3D vector struct.
    """

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = x
        self.y = y
        self.z = z


# =================================================================================================
#                            ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
# =================================================================================================
class Command:  # pylint: disable=too-many-instance-attributes
    """
    Command class to make a decision based on recieved telemetry,
    and send out commands based upon the data.
    """

    __private_key = object()

    @classmethod
    def create(
        cls,
        connection: mavutil.mavfile,
        target: Position,
        height_tolerance: float,
        z_speed: float,
        angle_tolerance: float,
        turning_speed: float,
        local_logger: logger.Logger,
    ) -> "tuple[bool, Command | None]":
        """
        Falliable create (instantiation) method to create a Command object.
        """
        return True, Command(
            cls.__private_key,
            connection,
            target,
            height_tolerance,
            z_speed,
            angle_tolerance,
            turning_speed,
            local_logger,
        )

    def __init__(
        self,
        key: object,
        connection: mavutil.mavfile,
        target: Position,
        height_tolerance: float,
        z_speed: float,
        angle_tolerance: float,
        turning_speed: float,
        local_logger: logger.Logger,
    ) -> None:
        assert key is Command.__private_key, "Use create() method"

        self.__connection = connection
        self.__target = target
        self.__height_tolerance = height_tolerance
        self.__z_speed = z_speed
        self.__angle_tolerance = angle_tolerance
        self.__turning_speed = turning_speed
        self.__logger = local_logger
        self.__velocity_sum = [0.0, 0.0, 0.0]
        self.__sample_count = 0

    def run(self, telemetry_data: telemetry.TelemetryData) -> "tuple[bool, list[str]]":
        """
        Make a decision based on received telemetry data.
        """
        # Log average velocity for this trip so far
        values = (
            telemetry_data.x,
            telemetry_data.y,
            telemetry_data.z,
            telemetry_data.yaw,
            telemetry_data.x_velocity,
            telemetry_data.y_velocity,
            telemetry_data.z_velocity,
        )
        if any(value is None for value in values):
            self.__logger.error("Telemetry data is incomplete")
            return False, []

        assert telemetry_data.x is not None
        assert telemetry_data.y is not None
        assert telemetry_data.z is not None
        assert telemetry_data.yaw is not None
        assert telemetry_data.x_velocity is not None
        assert telemetry_data.y_velocity is not None
        assert telemetry_data.z_velocity is not None

        self.__velocity_sum[0] += telemetry_data.x_velocity
        self.__velocity_sum[1] += telemetry_data.y_velocity
        self.__velocity_sum[2] += telemetry_data.z_velocity
        self.__sample_count += 1
        average_velocity = tuple(value / self.__sample_count for value in self.__velocity_sum)
        self.__logger.info(f"Average velocity: {average_velocity}")

        # Use COMMAND_LONG (76) message, assume the target_system=1 and target_componenet=0
        # The appropriate commands to use are instructed below

        # Adjust height using the comand MAV_CMD_CONDITION_CHANGE_ALT (113)
        # String to return to main: "CHANGE_ALTITUDE: {amount you changed it by, delta height in meters}"
        delta_z = self.__target.z - telemetry_data.z
        if abs(delta_z) > self.__height_tolerance:
            try:
                self.__connection.mav.command_long_send(
                    1,
                    0,
                    mavutil.mavlink.MAV_CMD_CONDITION_CHANGE_ALT,
                    0,
                    self.__z_speed,
                    0,
                    0,
                    0,
                    0,
                    0,
                    self.__target.z,
                )
            except (OSError, TypeError, ValueError) as exception:
                self.__logger.error(f"Failed to send altitude command: {exception}")
                return False, []
            return True, [f"CHANGE ALTITUDE: {delta_z}"]

        # Adjust direction (yaw) using MAV_CMD_CONDITION_YAW (115). Must use relative angle to current state
        # String to return to main: "CHANGING_YAW: {degree you changed it by in range [-180, 180]}"
        # Positive angle is counter-clockwise as in a right handed system
        desired_yaw = math.atan2(
            self.__target.y - telemetry_data.y,
            self.__target.x - telemetry_data.x,
        )
        yaw_delta = (desired_yaw - telemetry_data.yaw + math.pi) % (2 * math.pi) - math.pi
        yaw_delta_degrees = math.degrees(yaw_delta)
        if abs(yaw_delta_degrees) <= self.__angle_tolerance:
            return True, []

        direction = -1 if yaw_delta_degrees > 0 else 1
        try:
            self.__connection.mav.command_long_send(
                1,
                0,
                mavutil.mavlink.MAV_CMD_CONDITION_YAW,
                0,
                abs(yaw_delta_degrees),
                self.__turning_speed,
                direction,
                1,
                0,
                0,
                0,
            )
        except (OSError, TypeError, ValueError) as exception:
            self.__logger.error(f"Failed to send yaw command: {exception}")
            return False, []
        return True, [f"CHANGE YAW: {yaw_delta_degrees}"]


# =================================================================================================
#                            ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
# =================================================================================================
