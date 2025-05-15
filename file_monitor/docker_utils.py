# my_package/docker_utils.py
import os
from subprocess import run

from dotenv import load_dotenv
from loguru import logger
from file_monitor import config, state

# === Configuration ===
DOCKER_COMPOSE_PATH = config.DOCKER_COMPOSE_PATH
CONTAINER_NAME = config.CONTAINER_NAME


def start_container():
    """Starts the Docker container."""
    logger.info(f"Starting container {CONTAINER_NAME}")
    result = run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "up", "-d"])
    if result.returncode == 0:
        logger.info("Container started successfully.")
        return True
    else:
        logger.error("Failed to start container.")
    return False


def rebuild_container():
    """Rebuilds the Docker container."""
    if state.rebuild_lock.locked():
        logger.warning("Rebuild already in progress. Skipping.")
        return False

    with state.rebuild_lock:
        logger.info(f"Rebuilding container {CONTAINER_NAME}")
        result = run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "build"])
        if result.returncode == 0:
            logger.info("Container rebuilt successfully.")
            return True
        else:
            logger.error("Failed to rebuild container.")
        return False


def restart_container():
    """Restarts the Docker container."""
    logger.info(f"Restarting container {CONTAINER_NAME}")
    result = run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "restart", CONTAINER_NAME])
    if result.returncode == 0:
        logger.info("Container restarted successfully.")
        return True
    else:
        logger.error("Failed to restart container.")
    return False


def stop_container():
    """Stops the Docker container."""
    logger.info(f"Stopping container {CONTAINER_NAME}")
    run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "stop", CONTAINER_NAME])


def remove_container():
    """Removes the Docker container."""
    logger.info(f"Removing container {CONTAINER_NAME}")
    run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "rm", CONTAINER_NAME])
