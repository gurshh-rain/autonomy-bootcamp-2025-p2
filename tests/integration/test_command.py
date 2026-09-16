"""
Test the command worker with a mocked drone.
"""

import math
import multiprocessing as mp
import subprocess
import threading
import time

from pymavlink import mavutil

from modules.command import command
from modules.command import command_worker
from modules.common.modules.logger import logger
from modules.common.modules.logger import logger_main_setup
from modules.common.modules.read_yaml import read_yaml
from modules.telemetry import telemetry
from utilities.workers import queue_proxy_wrapper
from utilities.workers import worker_controller


MOCK_DRONE_MODULE = "tests.integration.mock_drones.command_drone"
CONNECTION_STRING = "tcp:localhost:12345"

# Please do not modify these, these are for the test cases (but do take note of them!)
TELEMETRY_PERIOD = 0.5
TARGET = command.Position(10, 20, 30)
HEIGHT_TOLERANCE = 0.5
Z_SPEED = 1  # m/s
ANGLE_TOLERANCE = 5  # deg
TURNING_SPEED = 5  # deg/s

# =================================================================================================
#                            ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
# =================================================================================================
# Add your own constants here

# =================================================================================================
#                            ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
# =================================================================================================


# Same utility functions across all the integration tests
# pylint: disable=duplicate-code
def start_drone() -> None:
    """
    Start the mocked drone.
    """
    subprocess.run(["python", "-m", MOCK_DRONE_MODULE], shell=True, check=False)


# =================================================================================================
#                            ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
# =================================================================================================
def stop(
    controller: worker_controller.WorkerController,
    input_queue: queue_proxy_wrapper.QueueProxyWrapper,
    output_queue: queue_proxy_wrapper.QueueProxyWrapper,
) -> None:
    """
    Stop the workers.
    """
    controller.request_exit()
    input_queue.queue.put(None)
    output_queue.queue.put(None)


def read_queue(
    output_queue: queue_proxy_wrapper.QueueProxyWrapper,
    main_logger: logger.Logger,
) -> None:
    """
    Read and print the output queue.
    """
    while True:
        value = output_queue.queue.get()
        if value is None:
            return
        main_logger.info(str(value))


def put_queue(
    path: "list[telemetry.TelemetryData]",
    input_queue: queue_proxy_wrapper.QueueProxyWrapper,
) -> None:
    """
    Place mocked inputs into the input queue periodically with period TELEMETRY_PERIOD.
    """
    for telemetry_data in path:
        input_queue.queue.put(telemetry_data)
        time.sleep(TELEMETRY_PERIOD)


# =================================================================================================
#                            ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
# =================================================================================================


def main() -> int:
    """
    Start the command worker simulation.
    """
    # Configuration settings
    result, config = read_yaml.open_config(logger.CONFIG_FILE_PATH)
    if not result:
        print("ERROR: Failed to load configuration file")
        return -1

    # Get Pylance to stop complaining
    assert config is not None

    # Setup main logger
    result, main_logger, _ = logger_main_setup.setup_main_logger(config)
    if not result:
        print("ERROR: Failed to create main logger")
        return -1

    # Get Pylance to stop complaining
    assert main_logger is not None

    # Mocked GCS, connect to mocked drone which is listening at CONNECTION_STRING
    # source_system = 255 (groundside)
    # source_component = 0 (ground control station)
    connection = mavutil.mavlink_connection(CONNECTION_STRING)
    connection.mav.heartbeat_send(
        mavutil.mavlink.MAV_TYPE_GCS,
        mavutil.mavlink.MAV_AUTOPILOT_INVALID,
        0,
        0,
        0,
    )
    main_logger.info("Connected!")
    # pylint: enable=duplicate-code

    # =============================================================================================
    #                          ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
    # =============================================================================================
    # Mock starting a worker, since cannot actually start a new process
    # Create a worker controller for your worker
    controller = worker_controller.WorkerController()

    # Create a multiprocess manager for synchronized queues
    mp_manager = mp.Manager()

    # Create your queues
    input_queue = queue_proxy_wrapper.QueueProxyWrapper(mp_manager, 1)
    output_queue = queue_proxy_wrapper.QueueProxyWrapper(mp_manager, 1)

    # Test cases, DO NOT EDIT!
    path = [
        # Test singular points
        telemetry.TelemetryData(x=0, y=0, z=29, yaw=0, x_velocity=0, y_velocity=0, z_velocity=4),
        telemetry.TelemetryData(x=0, y=0, z=31, yaw=0, x_velocity=0, y_velocity=0, z_velocity=-2),
        telemetry.TelemetryData(
            x=0, y=0, z=30.2, yaw=1.1071487177940904, x_velocity=0, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=0, y=0, z=29.8, yaw=1.1071487177940904, x_velocity=0, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=0, y=0, z=30, yaw=1.1071487177940904, x_velocity=0, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=0, y=0, z=30, yaw=1.142055302833977, x_velocity=0, y_velocity=0, z_velocity=0
        ),  # +2 degrees
        telemetry.TelemetryData(
            x=0, y=0, z=30, yaw=1.072242132754204, x_velocity=0, y_velocity=0, z_velocity=0
        ),  # -2 degrees
        # Fly a 30x30 square counter-clockwise
        telemetry.TelemetryData(x=0, y=0, z=30, yaw=0, x_velocity=0, y_velocity=20, z_velocity=0),
        telemetry.TelemetryData(x=10, y=0, z=30, yaw=0, x_velocity=0, y_velocity=20, z_velocity=0),
        telemetry.TelemetryData(x=20, y=0, z=30, yaw=0, x_velocity=0, y_velocity=20, z_velocity=0),
        telemetry.TelemetryData(
            x=30, y=0, z=30, yaw=math.pi / 2, x_velocity=20, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=30, y=10, z=30, yaw=math.pi / 2, x_velocity=20, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=30, y=20, z=30, yaw=math.pi / 2, x_velocity=20, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=30, y=30, z=30, yaw=math.pi, x_velocity=0, y_velocity=-20, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=20, y=30, z=30, yaw=-math.pi, x_velocity=0, y_velocity=-20, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=10, y=30, z=30, yaw=math.pi, x_velocity=0, y_velocity=-20, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=0, y=30, z=30, yaw=-math.pi / 2, x_velocity=-20, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=0, y=20, z=30, yaw=-math.pi / 2, x_velocity=-20, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=0, y=10, z=30, yaw=-math.pi / 2, x_velocity=-20, y_velocity=0, z_velocity=0
        ),
        # Fly 30x30 square clockwise
        telemetry.TelemetryData(
            x=0, y=0, z=30, yaw=math.pi / 2, x_velocity=0, y_velocity=20, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=0, y=10, z=30, yaw=math.pi / 2, x_velocity=0, y_velocity=20, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=0, y=20, z=30, yaw=math.pi / 2, x_velocity=0, y_velocity=20, z_velocity=0
        ),
        telemetry.TelemetryData(x=0, y=30, z=30, yaw=0, x_velocity=20, y_velocity=0, z_velocity=0),
        telemetry.TelemetryData(x=10, y=30, z=30, yaw=0, x_velocity=20, y_velocity=0, z_velocity=0),
        telemetry.TelemetryData(x=20, y=30, z=30, yaw=0, x_velocity=20, y_velocity=0, z_velocity=0),
        telemetry.TelemetryData(
            x=30, y=30, z=30, yaw=-math.pi / 2, x_velocity=0, y_velocity=-20, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=30, y=20, z=30, yaw=-math.pi / 2, x_velocity=0, y_velocity=-20, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=30, y=10, z=30, yaw=-math.pi / 2, x_velocity=0, y_velocity=-20, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=30, y=0, z=30, yaw=-math.pi, x_velocity=-20, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=20, y=0, z=30, yaw=math.pi, x_velocity=-20, y_velocity=0, z_velocity=0
        ),
        telemetry.TelemetryData(
            x=10, y=0, z=30, yaw=-math.pi, x_velocity=-20, y_velocity=0, z_velocity=0
        ),
    ]

    # Just set a timer to stop the worker after a while, since the worker infinite loops
    threading.Timer(
        TELEMETRY_PERIOD * len(path),
        stop,
        (controller, input_queue, output_queue),
    ).start()

    # Put items into input queue
    threading.Thread(target=put_queue, args=(path, input_queue)).start()

    # Read the main queue (worker outputs)
    threading.Thread(target=read_queue, args=(output_queue, main_logger)).start()

    command_worker.command_worker(
        connection,
        TARGET,
        HEIGHT_TOLERANCE,
        Z_SPEED,
        ANGLE_TOLERANCE,
        TURNING_SPEED,
        input_queue,
        output_queue,
        controller,
    )
    # =============================================================================================
    #                          ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
    # =============================================================================================

    return 0


if __name__ == "__main__":
    # Start drone in another process
    drone_process = mp.Process(target=start_drone)
    drone_process.start()

    result_main = main()
    if result_main < 0:
        print(f"Failed with return code {result_main}")
    else:
        print("Success!")

    drone_process.join()
