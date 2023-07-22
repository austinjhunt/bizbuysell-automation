import logging
import os
import traceback
import boto3 
import subprocess
import time
from selenium.common.exceptions import TimeoutException
from config import *
from bizbuysell import BizBuySellAutomator
from log import BaseLogger
from net import NetworkUtility


class Driver(BaseLogger):
    """ This module drives execution of the automation by 
    instantiating an automator object and calling its methods """
    def __init__(self, settings: dict = {}):
        """ 
        Args: 
        settings (dict) - settings parsed from a combination of a lambda event and 
        the environment variables (with priority given to lambda event in cases where 
        vars are defined in both places)
        """ 
        super().__init__(name="Driver")
        self.settings = settings
        self.lambda_client = boto3.client("lambda", region_name=self.settings['AWS_S3_REGION'])
        self.net = NetworkUtility()
        self.ip = self.net.get_public_ip() 

    def run_local(self, event, context ) -> dict:
        """Method to run the automation on a local server without AWS lambda.
        Uses environment variables instead of lambda event to drive execution"""
        self.info("Running local execution with values from environment variables") 

        if self.settings['MODE'] == 'single_user':
            try:
                # required variables are present
                assert all(
                    x is not None
                    for x in [
                        self.settings['SINGLE_USER_PASSWORD'],
                        self.settings['SINGLE_USER_USERNAME'],
                        self.settings['SINGLE_USER_CSV'],
                    ]
                )
            except AssertionError as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "error": (
                            "must provide SINGLE_USER_PASSWORD, "
                            "SINGLE_USER_USERNAME, and SINGLE_USER_CSV "
                            "as environment variables for single_user mode"
                        ),
                        "ip": self.ip,
                    },
                }
            self.info("Creating automator with MODE=single_user")
            try:
                automator = BizBuySellAutomator(network_utility=self.net)
                automator.init_driver()
                automator.automate_single_user_session(
                    username=self.settings['SINGLE_USER_USERNAME'],
                    password=self.settings['SINGLE_USER_PASSWORD'],
                    csv_path=self.settings['SINGLE_USER_CSV'],
                )
                automator.quit()
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "success": (
                            f"batch upload of {self.settings['SINGLE_USER_CSV']}"
                            f" complete for single_user {self.settings['SINGLE_USER_USERNAME']}"
                        ),
                        "ip": self.ip,
                    },
                }
            except TimeoutException as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc(), "ip": self.ip},
                }
            except Exception as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc(), "ip": self.ip},
                }

        elif self.settings['MODE'] == "multi_user":
            try:
                # required variable is present
                assert self.settings['MULTI_USER_CSV'] is not None
            except AssertionError as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "error": (
                            "must provide MULTI_USER_CSV as environment variable "
                            "for multi_user mode - csv should include "
                            "username,password,csv_path as columns"
                        ),
                        "ip": self.ip,
                    },
                }
            try:
                self.info("Creating automator with mode=multi_user")
                automator = BizBuySellAutomator(network_utility=self.net)
                automator.init_driver()
                if self.settings['FILE_SOURCE'] == "google_drive":
                    # Download the CSV for multi-user execution
                    # should be formatted as username,password,csv_path where
                    # csv_path is the batch upload file for that user
                    multi_user_csv_path = (
                        automator.gdrive_client.download_file_from_google_drive(
                            shared_link=self.settings['MULTI_USER_CSV'],
                            temporary_filename="multi-user-tmp.csv",
                        )
                    )
                elif self.settings['FILE_SOURCE'] == "local":
                    # use the local FS path to the file; csv_path column should also specify local FS paths
                    # for each user
                    multi_user_csv_path = self.settings['MULTI_USER_CSV']

                elif self.settings['FILE_SOURCE'] == "s3":
                    try:
                        # required variable is present
                        assert all(
                            x is not None for x in [
                                self.settings['AWS_S3_BUCKET'], 
                                self.settings['AWS_S3_REGION']]
                        )
                    except AssertionError as e:
                        self.error(traceback.format_exc())
                        return {
                            "statusCode": 500,
                            "headers": {"Content-Type": "application/json"},
                            "body": {
                                "error": (
                                    "must provide AWS_S3_REGION and AWS_S3_BUCKET if"
                                    " FILE_SOURCE=s3"
                                ),
                                "ip": self.ip,
                            },
                        }
                    multi_user_csv_path = (
                        automator.s3_client.download_file_from_s3_bucket(
                            bucket_name=self.settings['AWS_S3_BUCKET'],
                            file_key=self.settings['MULTI_USER_CSV'],
                            temporary_filename="multi-user-tmp.csv",
                        )
                    )

                automator.automate_multiple_user_sessions(
                    csv_file_path=multi_user_csv_path
                )
                automator.quit()
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"success": (f"batch uploads complete for multiple users")},
                }
            except TimeoutException as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc(), "ip": self.ip},
                }
            except Exception as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc(), "ip": self.ip},
                } 

    def run_lambda(self, event, context) -> None:
        """Run automation with AWS lambda using event to drive execution"""
        self.info("Running AWS Lambda execution with values from event")
        # Try to pull args from event first. If not present in event, then try environment variables.
        

        if self.settings["MODE"] == "single_user":
            try:
                # Required single user variables must be present
                assert all(
                    self.settings[f"SINGLE_USER_{x}"] is not None
                    for x in ["USERNAME", "PASSWORD", "CSV"]
                )
            except AssertionError as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "error": (
                            "must provide SINGLE_USER_PASSWORD, "
                            "SINGLE_USER_USERNAME, and SINGLE_USER_CSV "
                            "in body for single_user mode"
                        ),
                        "ip": self.ip,
                    },
                }
            self.info("Creating automator with MODE=single_user")
            try:
                automator = BizBuySellAutomator(network_utility=self.net)
                automator.init_driver()
                automator.automate_single_user_session(
                    username=self.settings["SINGLE_USER_USERNAME"],
                    password=self.settings["SINGLE_USER_PASSWORD"],
                    csv_path=self.settings["SINGLE_USER_CSV"],
                )
                automator.quit()
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "success": (
                            f'batch upload of {self.settings["SINGLE_USER_CSV"]}'
                            f" complete for single_user {self.settings['SINGLE_USER_USERNAME']}"
                        ),
                        "ip": self.ip,
                    },
                }
            except TimeoutException as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc(), "ip": self.ip},
                }
            except Exception as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc(), "ip": self.ip},
                }

        elif self.settings["MODE"] == "multi_user":
            try:
                assert self.settings["MULTI_USER_CSV"] is not None
            except AssertionError as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "error": (
                            "must provide MULTI_USER_CSV in body "
                            "for multi_user_mode - csv should include "
                            "username,password,csv_path as columns"
                        ),
                        "ip": self.ip,
                    },
                }
            try:
                self.info("Creating automator with MODE=multi_user")
                automator = BizBuySellAutomator(network_utility=self.net)
                automator.init_driver()
                if self.settings['FILE_SOURCE'] == "google_drive":
                    # Download the CSV for multi-user execution
                    # should be formatted as username,password,csv_path where
                    # csv_path is the batch upload file for that user
                    multi_user_csv_path = (
                        automator.gdrive_client.download_file_from_google_drive(
                            shared_link=self.settings["MULTI_USER_CSV"],
                            temporary_filename="multi-user-tmp.csv",
                        )
                    )
                elif self.settings['FILE_SOURCE'] == "local":
                    # use the local FS path to the file; csv_path column should also specify local FS paths
                    # for each user
                    multi_user_csv_path = self.settings['MULTI_USER_CSV']

                elif self.settings['FILE_SOURCE'] == "s3":
                    try:
                        # required variable is present
                        assert all(
                            x is not None for x in [
                                self.settings['AWS_S3_BUCKET'], 
                                self.settings['AWS_S3_REGION']
                                ]
                        )
                    except AssertionError as e:
                        self.error(traceback.format_exc())
                        return {
                            "statusCode": 500,
                            "headers": {"Content-Type": "application/json"},
                            "body": {
                                "error": (
                                    "must provide AWS_S3_REGION and AWS_S3_BUCKET if"
                                    " FILE_SOURCE=s3"
                                ),
                                "ip": self.ip,
                            },
                        }
                    multi_user_csv_path = (
                        automator.s3_client.download_file_from_s3_bucket(
                            bucket_name=self.settings['AWS_S3_BUCKET'],
                            file_key=self.settings['MULTI_USER_CSV'],
                            temporary_filename="multi-user-tmp.csv",
                        )
                    )

                automator.automate_multiple_user_sessions(
                    csv_file_path=multi_user_csv_path
                )
                automator.quit()
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "success": (f"batch uploads complete for multiple users"),
                        "ip": self.ip,
                    },
                }
            except TimeoutException as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc(), "ip": self.ip},
                }
            except Exception as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc(), "ip": self.ip},
                }
