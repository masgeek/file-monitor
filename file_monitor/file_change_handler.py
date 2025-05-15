import os
from watchdog.events import FileSystemEventHandler
from loguru import logger
from hashlib import sha1

from file_monitor import config
from file_monitor.docker_utils import rebuild_container, restart_container, remove_container, start_container, \
    stop_container


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.session_hashes = {}

        # Track Dockerfile separately if outside CODE_DIR
        self.extra_files = [config.DOCKERFILE_PATH]
        self.extra_hashes = {
            path: self._get_file_hash(path) for path in self.extra_files
        }

    def on_modified(self, event) -> None:
        if event.is_directory:
            return

        full_path = os.path.abspath(event.src_path)

        # Check if it's Dockerfile
        if full_path in self.extra_files:
            new_hash = self._get_file_hash(full_path)
            if new_hash != self.extra_hashes.get(full_path):
                logger.info(f"Dockerfile changed: {full_path}")
                self.extra_hashes[full_path] = new_hash
                result = rebuild_container()
                if result:
                    stop_container()
                    start_container()
            return

        # Regular source file handling
        if self._is_valid_file(full_path):
            rel_path = os.path.relpath(full_path, config.CODE_DIR)
            new_hash = self._get_file_hash(full_path)
            old_hash = self.session_hashes.get(rel_path)

            if new_hash != old_hash:
                self.session_hashes[rel_path] = new_hash
                file_name = os.path.basename(rel_path)

                logger.info(f"Detected change in: {rel_path}")

                if file_name in config.SPECIAL_FILES:
                    try:
                        choice = input(f"Rebuild due to special file {rel_path}? (y/n) [auto y]: ")
                    except Exception:
                        choice = 'y'
                    if choice.lower() in ['y', '']:
                        result = rebuild_container()
                        if result:
                            stop_container()
                            start_container()
                    else:
                        logger.info(f"Skipped rebuild for {rel_path}")
                else:
                    restart_container()

    def on_created(self, event):
        if not event.is_directory:
            self.on_modified(event)

    def on_deleted(self, event):
        if event.is_directory:
            return

        full_path = os.path.abspath(event.src_path)
        if full_path in self.extra_files:
            logger.warning(f"Dockerfile {full_path} was deleted.")
            self.extra_hashes[full_path] = "MISSING"
            return

        rel_path = os.path.relpath(full_path, config.CODE_DIR)
        logger.info(f"File deleted: {rel_path}")
        self.session_hashes.pop(rel_path, None)

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
