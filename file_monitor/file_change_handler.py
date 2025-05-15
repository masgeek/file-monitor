import os
import threading
from hashlib import sha1
from watchdog.events import PatternMatchingEventHandler
from loguru import logger

from file_monitor import config
from file_monitor import docker_utils


class FileChangeHandler(PatternMatchingEventHandler):
    def __init__(self):
        super().__init__(
            patterns=[f"*{ext}" for ext in config.FILE_EXTENSIONS],
            ignore_directories=True,
            case_sensitive=False
        )

        self.session_hashes = {}
        self.rebuild_timer = None
        self.rebuild_delay = config.REBUILD_DELAY

        self.extra_files = [os.path.abspath(config.DOCKERFILE_PATH)]
        self.extra_hashes = {
            path: self._get_file_hash(path) for path in self.extra_files
        }

    def on_modified(self, event):
        full_path = os.path.abspath(event.src_path)

        # Handle Dockerfile change
        if full_path in self.extra_files:
            new_hash = self._get_file_hash(full_path)
            if new_hash != self.extra_hashes.get(full_path):
                logger.info(f"Dockerfile changed: {full_path}")
                self.extra_hashes[full_path] = new_hash
                self._schedule_rebuild()
            return

        rel_path = os.path.relpath(full_path, config.CODE_DIR)
        new_hash = self._get_file_hash(full_path)
        old_hash = self.session_hashes.get(rel_path)

        if new_hash != old_hash:
            self.session_hashes[rel_path] = new_hash
            logger.info(f"Change detected in {rel_path}, scheduling rebuild...")
            self._schedule_rebuild()

    def on_created(self, event):
        self.on_modified(event)

    def on_deleted(self, event):
        full_path = os.path.abspath(event.src_path)
        if full_path in self.extra_files:
            logger.warning(f"Dockerfile {full_path} was deleted.")
            self.extra_hashes[full_path] = "MISSING"
        else:
            rel_path = os.path.relpath(full_path, config.CODE_DIR)
            logger.info(f"File deleted: {rel_path}")
            self.session_hashes.pop(rel_path, None)

    def _get_file_hash(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                return sha1(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to hash {filepath}: {e}")
            return "ERROR"

    def _schedule_rebuild(self):
        if self.rebuild_timer and self.rebuild_timer.is_alive():
            logger.debug("Rebuild already scheduled, skipping.")
            return

        def wrapped_rebuild():
            docker_utils.rebuild_and_launch_container()
            self.rebuild_timer = None

        self.rebuild_timer = threading.Timer(self.rebuild_delay, wrapped_rebuild)
        self.rebuild_timer.start()
