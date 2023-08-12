import os
import json

""" Configuration file for parsing environment variables into Python variables 
used by other modules """


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
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "FILE_TO_CREDS_JSON_MAP",
        ]
    }
    try:
        print("parsing JSON environment variable FILE_TO_CREDS_JSON_MAP")
        settings["FILE_TO_CREDS_JSON_MAP"] = json.loads(
            settings["FILE_TO_CREDS_JSON_MAP"]
        )
    except Exception as e:
        print("Error when parsing JSON environment variable FILE_TO_CREDS_JSON_MAP")
        print(e)
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
