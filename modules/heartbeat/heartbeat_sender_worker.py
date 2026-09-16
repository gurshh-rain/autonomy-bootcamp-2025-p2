"""
Heartbeat worker that sends heartbeats periodically.
"""

import os
import pathlib
import time

from pymavlink import mavutil

from utilities.workers import worker_controller
from . import heartbeat_sender
from ..common.modules.logger import logger


# =================================================================================================
#                            ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
# =================================================================================================
def heartbeat_sender_worker(
    connection: mavutil.mavfile,
    heartbeat_period: float,
    controller: worker_controller.WorkerController,
) -> None:
    """
    Worker process.

    connection is the MAVLink connection, heartbeat_period is the delay between heartbeats,
    and controller is how the main process communicates with this worker process.
    """
    # =============================================================================================
    #                          ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
    # =============================================================================================

    # Instantiate logger
    worker_name = pathlib.Path(__file__).stem
    process_id = os.getpid()
    result, local_logger = logger.Logger.create(f"{worker_name}_{process_id}", True)
    if not result:
        print("ERROR: Worker failed to create logger")
        return

    # Get Pylance to stop complaining
    assert local_logger is not None

    local_logger.info("Logger initialized", True)

    # =============================================================================================
    #                          ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
    # =============================================================================================
    # Instantiate class object (heartbeat_sender.HeartbeatSender)
    if heartbeat_period <= 0:
        local_logger.error("Heartbeat period must be greater than zero", True)
        return

    result, heartbeat_sender_instance = heartbeat_sender.HeartbeatSender.create(
        connection, local_logger
    )
    if not result:
        local_logger.error("Failed to create HeartbeatSender", True)
        return

    assert heartbeat_sender_instance is not None

    # Main loop: do work.
    while not controller.is_exit_requested():
        controller.check_pause()

        iteration_start = time.monotonic()
        heartbeat_sender_instance.run()
        elapsed = time.monotonic() - iteration_start
        time.sleep(max(0.0, heartbeat_period - elapsed))


# =================================================================================================
#                            ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
# =================================================================================================
