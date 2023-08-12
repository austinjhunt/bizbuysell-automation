import os
import boto3
from driver import Driver
from config import get_settings
import urllib.parse


def local_handler(event=None, context=None):
    # Use src.main.local_handler in docker-compose.yml to override
    # the default entrypoint (AWS Lambda) of main.lambda_handler
    # local execution ignores event and context
    settings = get_settings(event=event)
    settings["ENV"] = "local"
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


def is_triggered_by_s3(event):
    """Return true if triggered by an S3 update event (a file has been updated)"""
    triggered_by_s3 = False
    if "Records" in event:
        records = event["Records"]
        if len(records) > 0:
            record = records[0]
            triggered_by_s3 = record["eventSource"] == "aws:s3"
    return triggered_by_s3


def lambda_handler(event, context):
    """Primary handler function for AWS Lambda to execute. Referenced by Docker image
    entrypoint in Dockerfile (src.main.lambda_handler). Overridden
    with the above entrypoint for local non-lambda execution."""
    settings = get_settings(event=event)
    settings["ENV"] = "lambda"
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
    if is_triggered_by_s3(event):
        """
        Following 8/10/2023 meeting with Greg Cory, this function is set up as follows:
        - when file(s) are uploaded to S3, they trigger the execution of this lambda.
        IF triggered this way:
        - this lambda extracts the name (key) of the file from the event
        - assumption is MODE=single_user (since each individual file triggers execution)
        - this lambda extracts the credentials from the FILE_TO_CREDS_JSON_MAP
        which looks like {fileKey1: {username: x, password: y}, fileKey2: {username: x, password: y}, ... }
        - the lambda runs the single user mode execution with the S3 file as the CSV,
        and creds from the FILE_TO_CREDS_JSON_MAP env var as the corresponding creds
        """
        s3_event_details = event["Records"][0]["s3"]
        bucket_name = s3_event_details["bucket"]["name"]
        # received event file key is url encoded. decode before processing.
        s3_updated_file_key = urllib.parse.unquote_plus(
            s3_event_details["object"]["key"]
        )
        print(
            f"Triggered by S3 event (bucket: {bucket_name},file_key={s3_updated_file_key})."
            f"Calling S3 trigger handler with MODE=single_user"
        )
        return driver.handle_s3_trigger_single_user_mode(
            s3_bucket=bucket_name,
            s3_updated_file_key=s3_updated_file_key,
        )
    execution_result = driver.run_lambda(event, context)
    lambda_client = boto3.client("lambda", region_name=settings["AWS_S3_REGION"])
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
