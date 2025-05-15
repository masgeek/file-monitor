import os
import threading
from hashlib import sha1
from watchdog.events import PatternMatchingEventHandler
from loguru import logger

from file_monitor import config
from file_monitor.docker_utils import rebuild_then_start


class FileChangeHandler(PatternMatchingEventHandler):
    def __init__(self):
        # Use current file extensions from config
        patterns = [f"*{ext}" for ext in config.FILE_EXTENSIONS] + [os.path.basename(config.DOCKERFILE_PATH)]
        super().__init__(patterns=patterns, ignore_directories=True, case_sensitive=False)

        self.session_hashes = {}
        self.extra_files = [os.path.abspath(config.DOCKERFILE_PATH)]
        self.extra_hashes = {path: self._get_file_hash(path) for path in self.extra_files}

        self.rebuild_timer = None
        self.rebuild_delay = config.REBUILD_DELAY

        logger.info(f"Watching patterns: {patterns}, rebuild delay: {self.rebuild_delay}s")

    def on_modified(self, event):
        self._handle_event(event.src_path)

    def on_created(self, event):
        self._handle_event(event.src_path)

    def on_deleted(self, event):
        full_path = os.path.abspath(event.src_path)

        if full_path in self.extra_files:
            logger.error(f"Critical file deleted: {full_path}")
            self.extra_hashes[full_path] = "MISSING"
            return

        rel_path = os.path.relpath(full_path, config.CODE_DIR)
        logger.info(f"File deleted: {rel_path}")
        self.session_hashes.pop(rel_path, None)

    def _handle_event(self, full_path):
        full_path = os.path.abspath(full_path)

        # Handle Dockerfile specially
        if full_path in self.extra_files:
            new_hash = self._get_file_hash(full_path)
            if new_hash != self.extra_hashes.get(full_path):
                logger.info(f"Dockerfile changed: {full_path}")
                self.extra_hashes[full_path] = new_hash
                self._schedule_rebuild()
            return

        if not self._is_valid_file(full_path):
            return

        rel_path = os.path.relpath(full_path, config.CODE_DIR)
        new_hash = self._get_file_hash(full_path)
        old_hash = self.session_hashes.get(rel_path)

        if new_hash != old_hash:
            self.session_hashes[rel_path] = new_hash
            file_name = os.path.basename(rel_path)
            logger.info(f"Detected change in: {rel_path} ({file_name})")
            self._schedule_rebuild()

    def _is_valid_file(self, path):
        return (
                os.path.isfile(path)
                and not os.path.basename(path).startswith('.')
                and any(path.endswith(ext) for ext in config.FILE_EXTENSIONS)
        )

    def _get_file_hash(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                return sha1(f.read()).hexdigest()
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return "ERROR"

    def _schedule_rebuild(self):
        if self.rebuild_timer and self.rebuild_timer.is_alive():
            self.rebuild_timer.cancel()
            logger.debug("Existing rebuild timer canceled due to new change.")

        def do_rebuild():
            logger.info("Starting scheduled rebuild...")
            try:
                rebuild_then_start()
                logger.info("Rebuild and launch finished successfully.")
            except Exception as e:
                logger.error(f"Rebuild failed: {e}")
            finally:
                self.rebuild_timer = None

        self.rebuild_timer = threading.Timer(self.rebuild_delay, do_rebuild)
        self.rebuild_timer.start()
        logger.info(f"Rebuild scheduled in {self.rebuild_delay} seconds.")
