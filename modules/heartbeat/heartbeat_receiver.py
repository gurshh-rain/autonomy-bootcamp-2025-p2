"""
Heartbeat receiving logic.
"""

import time

from pymavlink import mavutil

from ..common.modules.logger import logger


# =================================================================================================
#                            ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
# =================================================================================================
class HeartbeatReceiver:
    """
    HeartbeatReceiver class to send a heartbeat
    """

    __private_key = object()

    @classmethod
    def create(
        cls,
        connection: mavutil.mavfile,
        heartbeat_period: float,
        disconnect_threshold: int,
        local_logger: logger.Logger,
    ) -> "tuple[bool, HeartbeatReceiver | None]":
        """
        Falliable create (instantiation) method to create a HeartbeatReceiver object.
        """
        if heartbeat_period <= 0 or disconnect_threshold <= 0:
            local_logger.error("Heartbeat settings must be greater than zero")
            return False, None
        return True, HeartbeatReceiver(
            cls.__private_key,
            connection,
            heartbeat_period,
            disconnect_threshold,
            local_logger,
        )

    def __init__(
        self,
        key: object,
        connection: mavutil.mavfile,
        heartbeat_period: float,
        disconnect_threshold: int,
        local_logger: logger.Logger,
    ) -> None:
        assert key is HeartbeatReceiver.__private_key, "Use create() method"

        self.__connection = connection
        self.__heartbeat_period = heartbeat_period
        self.__disconnect_threshold = disconnect_threshold
        self.__logger = local_logger
        self.__state = "Disconnected"
        self.__consecutive_misses = 0

    def run(self) -> "tuple[bool, str]":
        """
        Attempt to recieve a heartbeat message.
        If disconnected for over a threshold number of periods,
        the connection is considered disconnected.
        """
        start_time = time.monotonic()
        try:
            message = self.__connection.recv_match(
                type="HEARTBEAT",
                blocking=True,
                timeout=self.__heartbeat_period,
            )
        except (OSError, TypeError, ValueError) as exception:
            self.__logger.error(f"Failed to receive heartbeat: {exception}")
            return False, self.__state

        elapsed = time.monotonic() - start_time
        time.sleep(max(0.0, self.__heartbeat_period - elapsed))

        if message is not None:
            self.__state = "Connected"
            self.__consecutive_misses = 0
        else:
            self.__consecutive_misses += 1
            self.__logger.warning("Missed heartbeat")
            if self.__consecutive_misses >= self.__disconnect_threshold:
                self.__state = "Disconnected"

        return True, self.__state


# =================================================================================================
#                            ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
# =================================================================================================
