"""
Telemetry gathering logic.
"""

import time

from pymavlink import mavutil

from ..common.modules.logger import logger


class TelemetryData:  # pylint: disable=too-many-instance-attributes
    """
    Python struct to represent Telemtry Data. Contains the most recent attitude and position reading.
    """

    def __init__(
        self,
        time_since_boot: int | None = None,  # ms
        x: float | None = None,  # m
        y: float | None = None,  # m
        z: float | None = None,  # m
        x_velocity: float | None = None,  # m/s
        y_velocity: float | None = None,  # m/s
        z_velocity: float | None = None,  # m/s
        roll: float | None = None,  # rad
        pitch: float | None = None,  # rad
        yaw: float | None = None,  # rad
        roll_speed: float | None = None,  # rad/s
        pitch_speed: float | None = None,  # rad/s
        yaw_speed: float | None = None,  # rad/s
    ) -> None:
        self.time_since_boot = time_since_boot
        self.x = x
        self.y = y
        self.z = z
        self.x_velocity = x_velocity
        self.y_velocity = y_velocity
        self.z_velocity = z_velocity
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.roll_speed = roll_speed
        self.pitch_speed = pitch_speed
        self.yaw_speed = yaw_speed

    def __str__(self) -> str:
        return f"""{{
            time_since_boot: {self.time_since_boot},
            x: {self.x},
            y: {self.y},
            z: {self.z},
            x_velocity: {self.x_velocity},
            y_velocity: {self.y_velocity},
            z_velocity: {self.z_velocity},
            roll: {self.roll},
            pitch: {self.pitch},
            yaw: {self.yaw},
            roll_speed: {self.roll_speed},
            pitch_speed: {self.pitch_speed},
            yaw_speed: {self.yaw_speed}
        }}"""


# =================================================================================================
#                            ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
# =================================================================================================
class Telemetry:
    """
    Telemetry class to read position and attitude (orientation).
    """

    __private_key = object()

    @classmethod
    def create(
        cls,
        connection: mavutil.mavfile,
        timeout: float,
        local_logger: logger.Logger,
    ) -> "tuple[bool, Telemetry | None]":
        """
        Falliable create (instantiation) method to create a Telemetry object.
        """
        if timeout <= 0:
            local_logger.error("Telemetry timeout must be greater than zero")
            return False, None
        return True, Telemetry(cls.__private_key, connection, timeout, local_logger)

    def __init__(
        self,
        key: object,
        connection: mavutil.mavfile,
        timeout: float,
        local_logger: logger.Logger,
    ) -> None:
        assert key is Telemetry.__private_key, "Use create() method"

        self.__connection = connection
        self.__timeout = timeout
        self.__logger = local_logger

    def run(self) -> "tuple[bool, TelemetryData | None]":
        """
        Receive LOCAL_POSITION_NED and ATTITUDE messages from the drone,
        combining them together to form a single TelemetryData object.
        """
        # Read MAVLink message LOCAL_POSITION_NED (32)
        # Read MAVLink message ATTITUDE (30)
        # Return the most recent of both, and use the most recent message's timestamp
        attitude_message = None
        position_message = None
        deadline = time.monotonic() + self.__timeout

        try:
            while attitude_message is None or position_message is None:
                remaining_time = deadline - time.monotonic()
                if remaining_time <= 0:
                    self.__logger.error("Timed out while receiving telemetry")
                    return False, None

                message = self.__connection.recv_match(
                    type=["ATTITUDE", "LOCAL_POSITION_NED"],
                    blocking=True,
                    timeout=remaining_time,
                )
                if message is None:
                    time.sleep(max(0.0, deadline - time.monotonic()))
                    self.__logger.error("Timed out while receiving telemetry")
                    return False, None
                if message.get_type() == "ATTITUDE":
                    attitude_message = message
                else:
                    position_message = message
        except (OSError, TypeError, ValueError) as exception:
            self.__logger.error(f"Failed to receive telemetry: {exception}")
            return False, None

        return True, TelemetryData(
            time_since_boot=max(attitude_message.time_boot_ms, position_message.time_boot_ms),
            x=position_message.x,
            y=position_message.y,
            z=position_message.z,
            x_velocity=position_message.vx,
            y_velocity=position_message.vy,
            z_velocity=position_message.vz,
            roll=attitude_message.roll,
            pitch=attitude_message.pitch,
            yaw=attitude_message.yaw,
            roll_speed=attitude_message.rollspeed,
            pitch_speed=attitude_message.pitchspeed,
            yaw_speed=attitude_message.yawspeed,
        )


# =================================================================================================
#                            ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
# =================================================================================================
