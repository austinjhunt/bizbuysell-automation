import os
from driver import Driver
from config import get_settings
from net import NetworkUtility

def local_handler(event=None, context=None):
    # Use src.main.local_handler in docker-compose.yml to override
    # the default entrypoint (AWS Lambda) of main.lambda_handler
    # local execution ignores event and context
    driver = Driver()
    driver.run_local(event, context)


def lambda_handler(event, context):
    """Primary handler function for AWS Lambda to execute. Referenced by Docker image
    entrypoint in Dockerfile (src.main.lambda_handler). Overridden
    with the above entrypoint for local non-lambda execution."""
    settings = get_settings(event=event)
    if not settings['AWS_LAMBDA_ARN'] or not settings['AWS_LAMBDA_ECR_IMAGE_URI']:
        return {
            'statusCode': 500, 
            'body': {
                'error': 
                ('AWS_LAMBDA_ARN and AWS_LAMBDA_ECR_IMAGE_URI must be either '
                'stored as environment variables or passed in the event payload')
                
            }
        }
    driver = Driver(settings=settings)
    execution_result = driver.run_lambda(event, context)

    # Updating function code is non-blocking and triggers the
    # rotation to a new IP address on the next lambda execution
    print("Calling update_function_code(...) to trigger " "ip address rotation. ")
    driver.lambda_client.update_function_code(
        FunctionName=settings['AWS_LAMBDA_ARN'], ImageUri=settings['AWS_LAMBDA_ECR_IMAGE_URI']
    ) 
    return execution_result | {
        "ip": driver.net.get_public_ip(),
        "note": (
            "wait for at least 30 seconds before invoking again "
            "(for IP rotation via update_function_code)"
        ),
    }
