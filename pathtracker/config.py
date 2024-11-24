# config.py
import os
import sys
from pathlib import Path
import importlib.util

# Default paths
PT_BASE_DIR = Path.home()
PT_SHARED_PATH = '.local/share/paths'
PT_PATHS_DIR = PT_BASE_DIR / PT_SHARED_PATH

# Server-side configs
PT_SOCKET = '/tmp/path_tracker.sock'
PT_DB = 'paths.db'

# Database settings
PT_DB_PRAGMAS = ['journal_mode=WAL']

# Logging
PT_LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

def get_db_path():
    return PT_PATHS_DIR / PT_DB

def ensure_paths():
    PT_PATHS_DIR.mkdir(parents=True, exist_ok=True)

# Load custom configs if present
if 'PATHTRACKER_CONFIG' in os.environ:
    cfg_path = os.environ['PATHTRACKER_CONFIG']
    if not os.path.exists(cfg_path):
        print(f"Config file not found: {cfg_path}")
    try:
        module = sys.modules[__name__]
        spec = importlib.util.spec_from_file_location("pathtracker_config", cfg_path)
        override_conf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(override_conf)
        for key in dir(override_conf):
            if key.isupper():
                setattr(module, key, getattr(override_conf, key))
    except Exception as e:
        print(f"Failed to load config from {cfg_path}: {e}")