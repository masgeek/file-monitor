# my_package/docker_utils.py
import os
from time import sleep
from subprocess import run
from threading import Thread, Lock

from dotenv import load_dotenv
from loguru import logger
from file_monitor import config, state

_log_stream_lock = Lock()
_is_streaming_logs = False

# === Configuration ===
DOCKER_COMPOSE_PATH = config.DOCKER_COMPOSE_PATH
CONTAINER_NAME = config.CONTAINER_NAME


def build_container() -> bool:
    """Builds the Docker container."""
    logger.info(f"Building container {CONTAINER_NAME}")
    result = run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "build", CONTAINER_NAME, "--no-cache"])
    if result.returncode == 0:
        logger.info("Container built successfully.")
        return True
    else:
        logger.error("Failed to build container.")
        return False


def start_container() -> bool:
    """Starts the Docker container."""
    logger.info(f"Starting container {CONTAINER_NAME}")
    result = run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "up", "-d", CONTAINER_NAME])
    if result.returncode == 0:
        logger.info("Container started successfully.")
        return True
    else:
        logger.error("Failed to start container.")
        return False


def stop_container() -> bool:
    """Stops the Docker container."""
    logger.info(f"Stopping container {CONTAINER_NAME}")
    result = run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "stop", CONTAINER_NAME])
    return result.returncode == 0


def restart_container(show_logs: bool = True):
    """Restarts the Docker container."""
    logger.info(f"Restarting container {CONTAINER_NAME}")
    run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "restart", CONTAINER_NAME])
    if show_logs:
        _show_logs_in_background()


def rebuild_then_start(show_logs: bool = True):
    """Safely rebuilds and restarts the container, with optional log display."""
    if state.rebuild_lock.locked():
        logger.warning("Rebuild already in progress. Skipping.")
        return

    with state.rebuild_lock:
        if not stop_container():
            logger.error("Failed to stop container. Aborting rebuild.")
            return

        if not build_container():
            logger.error("Container build failed. Aborting start.")
            return

        if not start_container():
            logger.error("Container failed to start.")
            return

        if show_logs:
            _show_logs_in_background()

        logger.success("Rebuild and restart complete.")


def remove_container():
    """Removes the Docker container."""
    logger.info(f"Removing container {CONTAINER_NAME}")
    run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "rm", CONTAINER_NAME])


def _show_logs_in_background():
    global _is_streaming_logs

    if _is_streaming_logs:
        return

    def _logs():
        global _is_streaming_logs
        try:
            _is_streaming_logs = True
            logger.info(f"Streaming logs for {CONTAINER_NAME} (Ctrl+C to stop):")
            run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "logs", "-f", CONTAINER_NAME])
        except KeyboardInterrupt:
            logger.info("Stopped log stream.")
        finally:
            _is_streaming_logs = False

    Thread(target=_logs, daemon=True).start()
