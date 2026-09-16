"""
Bootcamp F2025

Main process to setup and manage all the other working processes
"""

import multiprocessing as mp
import queue
import time

from pymavlink import mavutil

from modules.common.modules.logger import logger
from modules.common.modules.logger import logger_main_setup
from modules.common.modules.read_yaml import read_yaml
from modules.command import command
from modules.command import command_worker
from modules.heartbeat import heartbeat_receiver_worker
from modules.heartbeat import heartbeat_sender_worker
from modules.telemetry import telemetry_worker
from utilities.workers import queue_proxy_wrapper
from utilities.workers import worker_controller
from utilities.workers import worker_manager


# MAVLink connection
CONNECTION_STRING = "tcp:localhost:12345"

# =================================================================================================
#                            ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
# =================================================================================================
# Set queue max sizes (<= 0 for infinity)
HEARTBEAT_TO_MAIN_QUEUE_MAX_SIZE = 1
TELEMETRY_TO_COMMAND_QUEUE_MAX_SIZE = 1
COMMAND_TO_MAIN_QUEUE_MAX_SIZE = 1

# Set worker counts
HEARTBEAT_SENDER_WORKER_COUNT = 1
HEARTBEAT_RECEIVER_WORKER_COUNT = 1
TELEMETRY_WORKER_COUNT = 1
COMMAND_WORKER_COUNT = 1

# Any other constants
HEARTBEAT_PERIOD = 1.0
DISCONNECT_THRESHOLD = 5
TELEMETRY_TIMEOUT = 1.0
RUN_DURATION = 100.0
TARGET = command.Position(10, 20, 30)
HEIGHT_TOLERANCE = 0.5
Z_SPEED = 1.0
ANGLE_TOLERANCE = 5.0
TURNING_SPEED = 5.0

# =================================================================================================
#                            ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
# =================================================================================================


def main() -> int:
    """
    Main function.
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

    # Create a connection to the drone. Assume that this is safe to pass around to all processes
    # In reality, this will not work, but to simplify the bootamp, preetend it is allowed
    # To test, you will run each of your workers individually to see if they work
    # (test "drones" are provided for you test your workers)
    # NOTE: If you want to have type annotations for the connection, it is of type mavutil.mavfile
    connection = mavutil.mavlink_connection(CONNECTION_STRING)
    connection.wait_heartbeat(timeout=30)  # Wait for the "drone" to connect

    # =============================================================================================
    #                          ↓ BOOTCAMPERS MODIFY BELOW THIS COMMENT ↓
    # =============================================================================================
    # Create a worker controller
    controller = worker_controller.WorkerController()

    # Create a multiprocess manager for synchronized queues
    mp_manager = mp.Manager()

    # Create queues
    heartbeat_to_main_queue = queue_proxy_wrapper.QueueProxyWrapper(
        mp_manager, HEARTBEAT_TO_MAIN_QUEUE_MAX_SIZE
    )

    telemetry_to_command_queue = queue_proxy_wrapper.QueueProxyWrapper(
        mp_manager, TELEMETRY_TO_COMMAND_QUEUE_MAX_SIZE
    )
    command_to_main_queue = queue_proxy_wrapper.QueueProxyWrapper(
        mp_manager, COMMAND_TO_MAIN_QUEUE_MAX_SIZE
    )

    # Create worker properties for each worker type (what inputs it takes, how many workers)
    # Heartbeat sender
    worker_settings = [
        (
            HEARTBEAT_SENDER_WORKER_COUNT,
            heartbeat_sender_worker.heartbeat_sender_worker,
            (connection, HEARTBEAT_PERIOD),
            [],
            [],
        ),
        # Heartbeat receiver
        (
            HEARTBEAT_RECEIVER_WORKER_COUNT,
            heartbeat_receiver_worker.heartbeat_receiver_worker,
            (connection, HEARTBEAT_PERIOD, DISCONNECT_THRESHOLD),
            [],
            [heartbeat_to_main_queue],
        ),
        # Telemetry
        (
            TELEMETRY_WORKER_COUNT,
            telemetry_worker.telemetry_worker,
            (connection, TELEMETRY_TIMEOUT),
            [],
            [telemetry_to_command_queue],
        ),
        # Command
        (
            COMMAND_WORKER_COUNT,
            command_worker.command_worker,
            (
                connection,
                TARGET,
                HEIGHT_TOLERANCE,
                Z_SPEED,
                ANGLE_TOLERANCE,
                TURNING_SPEED,
            ),
            [telemetry_to_command_queue],
            [command_to_main_queue],
        ),
    ]

    worker_properties = []
    for count, target, arguments, input_queues, output_queues in worker_settings:
        result, properties = worker_manager.WorkerProperties.create(
            count,
            target,
            arguments,
            input_queues,
            output_queues,
            controller,
            main_logger,
        )
        if not result or properties is None:
            main_logger.error("Failed to create worker properties")
            return -1
        worker_properties.append(properties)

    # Create the workers (processes) and obtain their managers
    worker_managers = []
    for properties in worker_properties:
        result, manager = worker_manager.WorkerManager.create(properties, main_logger)
        
        if not result or manager is None:
            main_logger.error("Failed to create worker manager")
            return -1
        worker_managers.append(manager)

    # Start worker processes
    for manager in worker_managers:
        manager.start_workers()

    main_logger.info("Started")

    # Main's work: read from all queues that output to main, and log any commands that we make
    # Continue running for 100 seconds or until the drone disconnects
    start_time = time.monotonic()
    disconnected = False

    while time.monotonic() - start_time < RUN_DURATION and not disconnected:
        try:
            state = heartbeat_to_main_queue.queue.get(timeout=0.1)
            main_logger.info(state)
            disconnected = state == "Disconnected"
        except queue.Empty:
            pass

        while True:
            try:
                message = command_to_main_queue.queue.get(block=False)
                main_logger.info(message)
            except queue.Empty:
                break

    # Stop the processes
    controller.request_exit()

    main_logger.info("Requested exit")

    # Fill and drain queues from END TO START
    command_to_main_queue.fill_and_drain_queue()
    telemetry_to_command_queue.fill_and_drain_queue()
    heartbeat_to_main_queue.fill_and_drain_queue()

    main_logger.info("Queues cleared")

    # Clean up worker processes
    for manager in worker_managers:
        manager.join_workers()

    main_logger.info("Stopped")

    # We can reset controller in case we want to reuse it
    # Alternatively, create a new WorkerController instance
    controller.clear_exit()

    # =============================================================================================
    #                          ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
    # =============================================================================================

    return 0


if __name__ == "__main__":
    result_main = main()
    if result_main < 0:
        print(f"Failed with return code {result_main}")
    else:
        print("Success!")
