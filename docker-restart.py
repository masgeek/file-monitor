import os
import time
import sqlite3
import hashlib
import subprocess
import signal
from dotenv import load_dotenv
from loguru import logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === Load Environment Variables from One Level Up ===
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

# === Configuration ===
DOCKERFILE_PATH = os.getenv("DOCKERFILE_PATH", "/home/masgeek/dev/r/akilimo-compute/Dockerfile")
CODE_DIR = os.getenv("CODE_DIR", "/home/masgeek/dev/r/akilimo-compute")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "akilimo-compute")
PROMPT_TIMEOUT = int(os.getenv("PROMPT_TIMEOUT", 120))
LOG_FILE = os.getenv("LOG_FILE", "./rebuild_log.txt")
HASH_DB_FILE = os.getenv("HASH_DB_FILE", "file_tracker.db")
SPECIAL_FILES = os.getenv("SPECIAL_FILES", "api.R,api-wrapper-orig.R").split(",")
DOCKER_COMPOSE_PATH = os.getenv("DOCKER_COMPOSE_PATH", "../docker-compose.yml")  # One directory up
FILE_EXTENSIONS = os.getenv("FILE_EXTENSIONS", ".R").split(",")  # List of file extensions to track

# === Logger Setup ===
logger.add(LOG_FILE, rotation="500 KB", retention="10 days", level="INFO")

# === Hash DB Functions ===
def setup_db():
    with sqlite3.connect(HASH_DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS file_hashes (
                            file_name TEXT PRIMARY KEY,
                            old_hash TEXT,
                            new_hash TEXT
                        )''')


def update_hash_in_db(file, old_hash, new_hash):
    with sqlite3.connect(HASH_DB_FILE) as conn:
        conn.execute('''INSERT OR REPLACE INTO file_hashes (file_name, old_hash, new_hash)
                        VALUES (?, ?, ?)''', (file, old_hash, new_hash))


def get_file_hash_from_db(file):
    with sqlite3.connect(HASH_DB_FILE) as conn:
        result = conn.execute("SELECT new_hash FROM file_hashes WHERE file_name = ?", (file,)).fetchone()
        return result[0] if result else None


# === Utility Functions ===
def get_file_hash(file):
    if os.path.isfile(file):
        with open(file, 'rb') as f:
            return hashlib.sha1(f.read()).hexdigest()
    return "MISSING"


def generate_file_hashes():
    hashes = {}
    for root, _, files in os.walk(CODE_DIR):
        for file in files:
            if any(file.endswith(ext) for ext in FILE_EXTENSIONS) and not file.startswith("."):
                rel_path = os.path.relpath(os.path.join(root, file), CODE_DIR)
                hashes[rel_path] = get_file_hash(os.path.join(root, file))
    return hashes


def cleanup(signal_num, frame):
    logger.info("Cleaning up...")
    subprocess.run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "down"])
    logger.info("Exiting script.")
    exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


# === Docker Actions ===
def rebuild_container():
    logger.info(f"Rebuilding container {CONTAINER_NAME}")
    subprocess.run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "down"])
    result = subprocess.run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "up", "-d", "--build", CONTAINER_NAME])
    if result.returncode == 0:
        logger.info("Container rebuilt successfully.")
        hashes = generate_file_hashes()
        for file, new_hash in hashes.items():
            old_hash = get_file_hash_from_db(file)
            update_hash_in_db(file, old_hash, new_hash)
    else:
        logger.error("Failed to rebuild container.")


def restart_container():
    logger.info(f"Restarting container {CONTAINER_NAME}")
    subprocess.run(["docker", "compose", "-f", DOCKER_COMPOSE_PATH, "restart", CONTAINER_NAME])
    hashes = generate_file_hashes()
    for file, new_hash in hashes.items():
        old_hash = get_file_hash_from_db(file)
        update_hash_in_db(file, old_hash, new_hash)


# === Watchdog Handler ===
class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return

        if any(event.src_path.endswith(ext) for ext in FILE_EXTENSIONS) and not event.src_path.startswith("."):
            rel_path = os.path.relpath(event.src_path, CODE_DIR)
            new_hash = get_file_hash(event.src_path)
            old_hash = get_file_hash_from_db(rel_path)
            if new_hash != old_hash:
                file_name = os.path.basename(rel_path)
                logger.info(f"Detected change of {file_name} in {rel_path}")
                if file_name in SPECIAL_FILES:
                    try:
                        choice = input(f"Rebuild due to change in special file {rel_path}? (y/n) [auto y]: ")
                    except Exception:
                        choice = 'y'
                    if choice.lower() in ['y', ''] :
                        rebuild_container()
                    else:
                        logger.info(f"Skipped rebuild for {rel_path}")
                else:
                    logger.info(f"Restart required due to change in {rel_path}")
                    restart_container()
                update_hash_in_db(rel_path, old_hash, new_hash)

    def on_created(self, event):
        if not event.is_directory:
            self.on_modified(event)

    def on_deleted(self, event):
        if event.is_directory:
            return
        rel_path = os.path.relpath(event.src_path, CODE_DIR)
        # logger.debug(f"File {rel_path} deleted")
        update_hash_in_db(rel_path, "", "MISSING")


# === Main Execution ===
def main():
    logger.info("Starting up the script for live reloading")
    setup_db()
    initial_hashes = generate_file_hashes()
    dockerfile_hash = get_file_hash(DOCKERFILE_PATH)
    for file, hash_val in initial_hashes.items():
        update_hash_in_db(file, "", hash_val)

    observer = Observer()
    observer.schedule(FileChangeHandler(), CODE_DIR, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == '__main__':
    main()
