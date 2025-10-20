import os
import logging

log = logging.getLogger(__name__)

# --- Mock State Configuration ---

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
MOCK_FILE_PATH = os.path.join(PROJECT_ROOT, "MOCK_DEVICE_ENABLED")

USE_MOCK = os.path.exists(MOCK_FILE_PATH)

if USE_MOCK:
    log.warning(
        f"Mock file found at '{MOCK_FILE_PATH}'. "
        "Instrument communication will be MOCKED."
    )
else:
    log.info("Running in LIVE (non-mock) instrument mode.")
