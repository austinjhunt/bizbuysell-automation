import os 
""" Configuration file for storing variables used by other modules. Primarily for parsing environment variables into Python variables """

FILE_SOURCE = os.environ.get("FILE_SOURCE", "google_drive")  # alternative is local
PRODUCTION = os.environ.get("PRODUCTION", "0") == "1"
TEMP_FOLDER = "/tmp" if PRODUCTION else os.path.dirname(__file__)
WEBDRIVER_TIMEOUT_SECONDS = int(os.environ.get("WEBDRIVER_TIMEOUT_SECONDS", "15"))
WEBDRIVER_UPLOAD_TIMEOUT_SECONDS = int(
    os.environ.get("WEBDRIVER_UPLOAD_TIMEOUT_SECONDS", "30")
)
DEV_CHROME_PATH = os.path.join(os.path.dirname(__file__), "chrome-dev", "chrome.exe")
DEV_CHROME_DRIVER_PATH = os.path.join(
    os.path.dirname(__file__), "chrome-dev", "chromedriver.exe"
)
VERBOSE = os.environ.get("VERBOSE", "0") == "1"
MODE = os.environ.get("MODE", "single_user")
MULTI_USER_CSV = os.environ.get("MULTI_USER_CSV", "")

SINGLE_USER_USERNAME = os.environ.get("SINGLE_USER_USERNAME", "")
SINGLE_USER_PASSWORD = os.environ.get("SINGLE_USER_PASSWORD", "")
SINGLE_USER_CSV = os.environ.get("SINGLE_USER_CSV", "")