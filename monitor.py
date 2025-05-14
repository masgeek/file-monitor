import os
import time
import sqlite3
import hashlib
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# === Configuration ===
DOCKERFILE_PATH = "./Dockerfile"
CODE_DIR = os.path.join("/", "home", "masgeek", "projects", "akilimo-compute")
CONTAINER_NAME = "akilimo-compute"
PROMPT_TIMEOUT = 120
LOG_FILE = "./rebuild_log.txt"
HASH_DB_FILE = "file_tracker.sqlite"

# === Runtime State ===
BANNER = "=========="
R_FILE_HASHES = {}
LAST_R_HASHES = {}
SPECIAL_FILES = ["api.R", "api-wrapper-orig.R"]


# === SQLite Functions ===
def setup_db():
    conn = sqlite3.connect(HASH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS file_hashes
                      (
                          file_name
                          TEXT
                          PRIMARY
                          KEY,
                          old_hash
                          TEXT,
                          new_hash
                          TEXT
                      )''')
    conn.commit()
    conn.close()


def update_hash_in_db(file, old_hash, new_hash):
    conn = sqlite3.connect(HASH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO file_hashes (file_name, old_hash, new_hash)
        VALUES (?, ?, ?)
    ''', (file, old_hash, new_hash))
    conn.commit()
    conn.close()


def get_file_hash_from_db(file):
    conn = sqlite3.connect(HASH_DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT new_hash FROM file_hashes WHERE file_name = ?", (file,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


# === Cleanup ===
def cleanup(signal, frame):
    print("\n[INFO] Cleaning up...")
    subprocess.run(["docker", "compose", "down"])
    print("[INFO] Exiting script.")
    exit(0)


import signal

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


# === Hashing Functions ===
def get_file_hash(file):
    if os.path.isfile(file):
        return hashlib.sha1(open(file, 'rb').read()).hexdigest()
    return "MISSING"


def generate_r_file_hashes():
    global R_FILE_HASHES
    R_FILE_HASHES = {}
    for root, _, files in os.walk(CODE_DIR):
        for file in files:
            if file.endswith(".R") and not file.startswith("."):
                rel_path = os.path.relpath(os.path.join(root, file), CODE_DIR)
                hash_value = get_file_hash(os.path.join(root, file))
                R_FILE_HASHES[rel_path] = hash_value


# === Actions ===
def rebuild_container():
    print(f"\n{BANNER} {time.ctime()} - Rebuilding container {CONTAINER_NAME} {BANNER}")
    subprocess.run(["docker", "compose", "down"])
    result = subprocess.run(["docker", "compose", "up", "-d", "--build", CONTAINER_NAME])
    if result.returncode == 0:
        print(f"[INFO] {time.ctime()} Container rebuilt successfully.")
        generate_r_file_hashes()
        for file, new_hash in R_FILE_HASHES.items():
            old_hash = get_file_hash_from_db(file)
            update_hash_in_db(file, old_hash, new_hash)
    else:
        print(f"[ERROR] {time.ctime()} Failed to rebuild container.")


def restart_container():
    print(f"\n{BANNER} {time.ctime()} - Restarting container {CONTAINER_NAME} {BANNER}")
    subprocess.run(["docker", "compose", "restart", CONTAINER_NAME])
    generate_r_file_hashes()
    for file, new_hash in R_FILE_HASHES.items():
        old_hash = get_file_hash_from_db(file)
        update_hash_in_db(file, old_hash, new_hash)


# === Watchdog Handler ===
class FileChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return

        if event.src_path.endswith(".R") and not event.src_path.startswith("."):
            rel_path = os.path.relpath(event.src_path, CODE_DIR)
            new_hash = get_file_hash(event.src_path)
            old_hash = get_file_hash_from_db(rel_path)
            if new_hash != old_hash:
                print(f"[CHANGE] Detected change in {rel_path} at {time.ctime()}")
                if rel_path in SPECIAL_FILES:
                    choice = input(f"[Prompt] Rebuild due to change in special file {rel_path}? (y/n) [auto y]: ")
                    if choice.lower() in ['y', '']:
                        rebuild_container()
                    else:
                        print(f"[INFO] Skipped rebuild due to {rel_path} change.")
                else:
                    print(f"[INFO] Restart required due to change in {rel_path}.")
                    restart_container()
                update_hash_in_db(rel_path, old_hash, new_hash)

    def on_created(self, event):
        if event.is_directory:
            return
        self.on_modified(event)

    def on_deleted(self, event):
        if event.is_directory:
            return
        rel_path = os.path.relpath(event.src_path, CODE_DIR)
        print(f"[INFO] File {rel_path} deleted at {time.ctime()}")
        update_hash_in_db(rel_path, "", "MISSING")


# === Initialization ===
print(f"\n{BANNER} {time.ctime()} - Starting up {BANNER}")
setup_db()
generate_r_file_hashes()

DOCKERFILE_HASH = get_file_hash(DOCKERFILE_PATH)
for file, new_hash in R_FILE_HASHES.items():
    update_hash_in_db(file, "", new_hash)

# === Watchdog Observer ===
event_handler = FileChangeHandler()
observer = Observer()
observer.schedule(event_handler, CODE_DIR, recursive=True)
observer.start()

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    observer.stop()

observer.join()
