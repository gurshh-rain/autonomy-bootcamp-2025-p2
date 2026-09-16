"""
Test the heartbeat reciever worker with a mocked drone.
"""

import multiprocessing as mp
import subprocess
import threading

from pymavlink import mavutil

from modules.common.modules.logger import logger
from modules.common.modules.logger import logger_main_setup
from modules.common.modules.read_yaml import read_yaml
from modules.heartbeat import heartbeat_receiver_worker
from utilities.workers import queue_proxy_wrapper
from utilities.workers import worker_controller


MOCK_DRONE_MODULE = "tests.integration.mock_drones.heartbeat_receiver_drone"
CONNECTION_STRING = "tcp:localhost:12345"

# Please do not modify these, these are for the test cases (but do take note of them!)
HEARTBEAT_PERIOD = 1
NUM_TRIALS = 5
NUM_DISCONNECTS = 3
DISCONNECT_THRESHOLD = 5
ERROR_TOLERANCE = 1e-2

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
    output_queue: queue_proxy_wrapper.QueueProxyWrapper,
) -> None:
    """
    Stop the workers.
    """
    controller.request_exit()
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


# =================================================================================================
#                            ↑ BOOTCAMPERS MODIFY ABOVE THIS COMMENT ↑
# =================================================================================================


def main() -> int:
    """
    Start the heartbeat receiver worker simulation.
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
    output_queue = queue_proxy_wrapper.QueueProxyWrapper(mp_manager, 1)

    # Just set a timer to stop the worker after a while, since the worker infinite loops
    threading.Timer(
        HEARTBEAT_PERIOD * (NUM_TRIALS * 2 + DISCONNECT_THRESHOLD + NUM_DISCONNECTS + 2),
        stop,
        (controller, output_queue),
    ).start()

    # Read the main queue (worker outputs)
    threading.Thread(target=read_queue, args=(output_queue, main_logger)).start()

    heartbeat_receiver_worker.heartbeat_receiver_worker(
        connection,
        HEARTBEAT_PERIOD,
        DISCONNECT_THRESHOLD,
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
