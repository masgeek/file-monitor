# my_package/__main__.py

import signal
import time
from loguru import logger
from watchdog.observers import Observer

from file_monitor.file_change_handler import FileChangeHandler
from file_monitor.config import CODE_DIR
from file_monitor.docker_utils import stop_container


def cleanup(observer):
    logger.info("Stopping observer and cleaning up...")
    observer.stop()
    observer.join()
    logger.info("Shutdown complete.")


def main():
    logger.info("Starting file watcher...")

    observer = Observer()
    handler = FileChangeHandler()
    observer.schedule(handler, CODE_DIR, recursive=True)
    observer.start()

    def handle_sigterm(signum, frame):
        cleanup(observer)
        exit(0)

    signal.signal(signal.SIGINT, handle_sigterm)
    # signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup(observer)


if __name__ == "__main__":
    main()
