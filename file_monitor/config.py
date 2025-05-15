import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'))

# === Configuration ===
DOCKERFILE_PATH = os.getenv("DOCKERFILE_PATH", "/home/masgeek/dev/r/akilimo-compute/Dockerfile")
CODE_DIR = os.getenv("CODE_DIR", "/home/masgeek/dev/r/akilimo-compute")
CONTAINER_NAME = os.getenv("CONTAINER_NAME", "akilimo-compute")
PROMPT_TIMEOUT = int(os.getenv("PROMPT_TIMEOUT", 120))
LOG_FILE = os.getenv("LOG_FILE", "./rebuild_log.txt")
HASH_DB_FILE = os.getenv("HASH_DB_FILE", "file_tracker.db")
SPECIAL_FILES = os.getenv("SPECIAL_FILES", "api.R,api-wrapper-orig.R").split(",")
DOCKER_COMPOSE_PATH = os.getenv("DOCKER_COMPOSE_PATH", "docker-compose.yml")  # One directory up
FILE_EXTENSIONS = os.getenv("FILE_EXTENSIONS", ".R").split(",")  # List of file extensions to track
