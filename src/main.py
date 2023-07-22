import os
import boto3 
from driver import Driver
from config import get_settings
from net import NetworkUtility

def local_handler(event=None, context=None):
    # Use src.main.local_handler in docker-compose.yml to override
    # the default entrypoint (AWS Lambda) of main.lambda_handler
    # local execution ignores event and context
    settings = get_settings(event=event)
    settings['env'] = 'local'
    driver = Driver(settings=settings)

    # If running locally AND using S3 as a file source, you
    # must provide AWS_SECRET_ACCESS_KEY and AWS_ACCESS_KEY_ID
    # arguments either as environment variables or as event
    # payload params. That is the ONLY time they should be provided.
    if settings["FILE_SOURCE"] == "s3":
        if (
            settings["AWS_ACCESS_KEY_ID"] is None
            or settings["AWS_SECRET_ACCESS_KEY"] is None
        ):
            return {
                "statusCode": 500,
                "body": {
                    "error": (
                        "When running outside of Lambda with FILE_SOURCE=s3, "
                        "you must provide AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
                        "as environment variables or in event payload"
                    )
                },
            }

    return driver.run_local(event, context)


def lambda_handler(event, context):
    """Primary handler function for AWS Lambda to execute. Referenced by Docker image
    entrypoint in Dockerfile (src.main.lambda_handler). Overridden
    with the above entrypoint for local non-lambda execution."""
    settings = get_settings(event=event)
    settings['env'] = 'lambda'
    if not settings["AWS_LAMBDA_ARN"] or not settings["AWS_LAMBDA_ECR_IMAGE_URI"]:
        return {
            "statusCode": 500,
            "body": {
                "error": (
                    "AWS_LAMBDA_ARN and AWS_LAMBDA_ECR_IMAGE_URI must be either "
                    "stored as environment variables or passed in the event payload"
                )
            },
        }
    driver = Driver(settings=settings)
    execution_result = driver.run_lambda(event, context)
    lambda_client = boto3.client("lambda", region_name=settings['AWS_S3_REGION'])
    # Updating function code is non-blocking and triggers the
    # rotation to a new IP address on the next lambda execution
    print("Calling update_function_code(...) to trigger " "ip address rotation. ")
    lambda_client.update_function_code(
        FunctionName=settings["AWS_LAMBDA_ARN"],
        ImageUri=settings["AWS_LAMBDA_ECR_IMAGE_URI"],
    )
    return execution_result | {
        "ip": driver.net.get_public_ip(),
        "note": (
            "wait for at least 30 seconds before invoking again "
            "(for IP rotation via update_function_code)"
        ),
    }
