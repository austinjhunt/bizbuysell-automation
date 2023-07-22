import os

""" Configuration file for parsing environment variables into Python variables 
used by other modules """


WEBDRIVER_TIMEOUT_SECONDS = int(os.environ.get("WEBDRIVER_TIMEOUT_SECONDS", "15"))
WEBDRIVER_UPLOAD_TIMEOUT_SECONDS = int(
    os.environ.get("WEBDRIVER_UPLOAD_TIMEOUT_SECONDS", "30")
)

VERBOSE = os.environ.get("VERBOSE", "0") == "1"
MODE = os.environ.get("MODE", "single_user")
SINGLE_USER_USERNAME = os.environ.get("SINGLE_USER_USERNAME", None)
SINGLE_USER_PASSWORD = os.environ.get("SINGLE_USER_PASSWORD", None)
SINGLE_USER_CSV = os.environ.get("SINGLE_USER_CSV", None)
MULTI_USER_CSV = os.environ.get("MULTI_USER_CSV", None)
AWS_S3_REGION = os.environ.get("AWS_S3_REGION", None)
AWS_S3_BUCKET = os.environ.get("AWS_S3_BUCKET", None)
AWS_LAMBDA_ARN = os.environ.get("AWS_LAMBDA_ARN", None)
AWS_LAMBDA_ECR_IMAGE_URI = os.environ.get("AWS_LAMBDA_ECR_IMAGE_URI", None)
FILE_SOURCE = os.environ.get("FILE_SOURCE", "google_drive")  # alternative is local
PRODUCTION = os.environ.get("PRODUCTION", "0") == "1"
VERBOSE = os.environ.get("VERBOSE", "0") == "1"


def get_settings(event: dict = {}):
    """
    Try to pull settings from Lambda event first. If not
    present in event, then use environment variables.
    This gives the option of passing the driving arguments
    either via environment variables or via event keys.
    args:
    event (dict) - lambda event
    returns:
    settings (dict) - a dictionary that contains the values for each main variable
    with priority given to the event in case a variable is defined by
    both the environment and the event
    """
    settings = {
        x: os.environ.get(x, None) if not event.get(x, None) else event.get(x, None)
        for x in [
            "MODE",
            "SINGLE_USER_USERNAME",
            "SINGLE_USER_PASSWORD",
            "SINGLE_USER_CSV",
            "MULTI_USER_CSV",
            "AWS_S3_REGION",
            "AWS_S3_BUCKET",
            "AWS_LAMBDA_ARN",
            "AWS_LAMBDA_ECR_IMAGE_URI",
            "FILE_SOURCE",
        ]
    }
    # now handle the ints
    settings = settings | {
        "WEBDRIVER_TIMEOUT_SECONDS": int(
            os.environ.get("WEBDRIVER_TIMEOUT_SECONDS", "15")
        ),
        "WEBDRIVER_UPLOAD_TIMEOUT_SECONDS": int(
            os.environ.get("WEBDRIVER_UPLOAD_TIMEOUT_SECONDS", "30")
        ),
    }
    # handle bools
    settings = settings | {
        x: os.environ.get(x, "0") == "1" for x in ["VERBOSE", "PRODUCTION"]
    }

    # handle constants
    settings = settings | {
        "TEMP_FOLDER": "/tmp" if settings["PRODUCTION"] else os.path.dirname(__file__),
        "CHROME_PATH": "/opt/chrome/chrome"
        if settings["PRODUCTION"]
        else os.path.join(os.path.dirname(__file__), "chrome-dev", "chrome.exe"),
        "CHROME_DRIVER_PATH": "/opt/chromedriver"
        if settings["PRODUCTION"]
        else os.path.join(os.path.dirname(__file__), "chrome-dev", "chromedriver.exe"),
    }
    return settings
