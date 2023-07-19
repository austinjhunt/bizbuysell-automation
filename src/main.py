
import os 
from config import VERBOSE
from driver import Driver
 
def local_handler(event=None, context=None):
    # Use main.local_handler in docker-compose.yml to override
    # the default entrypoint (AWS Lambda) of main.lambda_handler
    # local execution ignores event and context
    verbose = os.environ.get("VERBOSE", "0") == "1"
    driver = Driver(verbose=VERBOSE)
    driver.run_local()


def lambda_handler(event, context):
    """Primary handler function for AWS Lambda to execute. Referenced by Docker image
    entrypoint in Dockerfile (main.lambda_handler). Overridden
    with the above entrypoint for local non-lambda execution."""
    verbose = False
    if "verbose" in event:
        verbose = event["verbose"]
    driver = Driver(verbose=verbose)
    driver.run_lambda(event, context)
