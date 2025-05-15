# my_package/state.py
import threading

# Shared rebuild lock
rebuild_lock = threading.Lock()
