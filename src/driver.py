import logging
import os
import csv
import subprocess
import time
from selenium.common.exceptions import TimeoutException
from bizbuysell import BizBuySellAutomator
from log import BaseLogger
from net import NetworkUtility


class Driver(BaseLogger):
    """This module drives execution of the automation by
    instantiating an automator object and calling its methods"""

    def __init__(self, settings: dict = {}):
        """
        Args:
        settings (dict) - settings parsed from a combination of a lambda event and
        the environment variables (with priority given to lambda event in cases where
        vars are defined in both places)
        """
        super().__init__(name="Driver", settings=settings)
        self.net = NetworkUtility(settings=settings)
        self.ip = self.net.get_public_ip()
        self.info(
            {
                "method": "Driver.__init__",
                "args": {"settings": "***"},
                "message": "Initializing Driver",
            }
        )

    def run_local(self, event, context) -> dict:
        """Method to run the automation on a local server without AWS lambda.
        Uses environment variables instead of lambda event to drive execution"""
        self.info(
            {
                "method": "Driver.run_local",
                "args": {"event": event, "context": context},
                "message": "Running local execution with values from environment variables",
            }
        )
        if self.settings["MODE"] == "single_user":
            try:
                # required variables are present
                assert all(
                    x is not None
                    for x in [
                        self.settings["SINGLE_USER_PASSWORD"],
                        self.settings["SINGLE_USER_USERNAME"],
                        self.settings["SINGLE_USER_CSV"],
                    ]
                )
            except AssertionError as e:
                self.error(
                    {
                        "method": "Driver.run_local",
                        "message": "Missing required environment variables for single_user mode",
                        "error": str(e),
                    }
                )
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
            self.info(
                {
                    "method": "Driver.run_local",
                    "message": "Creating automator with MODE=single_user",
                }
            )
            try:
                automator = BizBuySellAutomator(
                    network_utility=self.net, settings=self.settings
                )
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
                            f"batch upload of {self.settings['SINGLE_USER_CSV']}"
                            f" complete for single_user {self.settings['SINGLE_USER_USERNAME']}"
                        ),
                        "ip": self.ip,
                    },
                }
            except TimeoutException as e:
                self.error(
                    {
                        "method": "Driver.run_local",
                        "message": "TimeoutException",
                        "error": str(e),
                    }
                )
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": str(e), "ip": self.ip},
                }
            except Exception as e:
                self.error(
                    {
                        "method": "Driver.run_local",
                        "message": "Exception",
                        "error": str(e),
                    }
                )
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": str(e), "ip": self.ip},
                }

        elif self.settings["MODE"] == "multi_user":
            try:
                # required variable is present
                assert self.settings["MULTI_USER_CSV"] is not None
            except AssertionError as e:
                self.error(
                    {
                        "method": "Driver.run_local",
                        "message": "Missing required environment variables for multi_user mode",
                        "error": str(e),
                    }
                )
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
                self.info(
                    {
                        "method": "Driver.run_local",
                        "message": "Creating automator with MODE=multi_user",
                    }
                )
                automator = BizBuySellAutomator(
                    network_utility=self.net, settings=self.settings
                )
                automator.init_driver()
                if self.settings["FILE_SOURCE"] == "google_drive":
                    # Download the CSV for multi-user execution
                    # should be formatted as username,password,csv_path where
                    # csv_path is the batch upload file for that user
                    multi_user_csv_path = (
                        automator.gdrive_client.download_file_from_google_drive(
                            shared_link=self.settings["MULTI_USER_CSV"],
                            temporary_filename="multi-user-tmp.csv",
                        )
                    )
                elif self.settings["FILE_SOURCE"] == "local":
                    # use the local FS path to the file; csv_path column should also specify local FS paths
                    # for each user
                    multi_user_csv_path = self.settings["MULTI_USER_CSV"]

                elif self.settings["FILE_SOURCE"] == "s3":
                    try:
                        # required variable is present
                        assert all(
                            x is not None
                            for x in [
                                self.settings["AWS_S3_BUCKET"],
                                self.settings["AWS_S3_REGION"],
                            ]
                        )
                    except AssertionError as e:
                        self.error(
                            {
                                "method": "Driver.run_local",
                                "message": "Missing AWS S3 environment variables for multi_user mode",
                                "error": str(e),
                            }
                        )
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
                            bucket_name=self.settings["AWS_S3_BUCKET"],
                            file_key=self.settings["MULTI_USER_CSV"],
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
                self.error(
                    {
                        "method": "Driver.run_local",
                        "message": "TimeoutException in multi_user mode",
                        "error": str(e),
                    }
                )
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": str(e), "ip": self.ip},
                }
            except Exception as e:
                self.error(
                    {
                        "method": "Driver.run_local",
                        "message": "Exception in multi_user mode",
                        "error": str(e),
                    }
                )
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": str(e), "ip": self.ip},
                }

    def run_lambda(self, event, context) -> None:
        """Run automation with AWS lambda using event to drive execution"""
        self.info(
            {
                "method": "Driver.run_lambda",
                "message": "Running AWS Lambda execution with values from event",
            }
        )
        # Try to pull args from event first. If not present in event, then try environment variables.
        if self.settings["MODE"] == "single_user":
            try:
                # Required single user variables must be present
                assert all(
                    self.settings[f"SINGLE_USER_{x}"] is not None
                    for x in ["USERNAME", "PASSWORD", "CSV"]
                )
            except AssertionError as e:
                self.error(
                    {
                        "method": "Driver.run_lambda",
                        "message": "Missing required environment variables for single_user mode",
                        "error": str(e),
                    }
                )
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
            try:
                self.info(
                    {
                        "method": "Driver.run_lambda",
                        "message": "Creating automator with MODE=single_user",
                    }
                )
                automator = BizBuySellAutomator(
                    network_utility=self.net, settings=self.settings
                )
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
                self.error(
                    {
                        "method": "Driver.run_lambda",
                        "message": "TimeoutException in single_user mode",
                        "error": str(e),
                    }
                )
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": str(e), "ip": self.ip},
                }
            except Exception as e:
                self.error(
                    {
                        "method": "Driver.run_lambda",
                        "message": "Exception in single_user mode",
                        "error": str(e),
                    }
                )
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": str(e), "ip": self.ip},
                }

        elif self.settings["MODE"] == "multi_user":
            try:
                assert self.settings["MULTI_USER_CSV"] is not None
            except AssertionError as e:
                self.error(
                    {
                        "method": "Driver.run_lambda",
                        "message": "Missing required environment variables for multi_user mode",
                        "error": str(e),
                    }
                )
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
                self.info(
                    {
                        "method": "Driver.run_lambda",
                        "message": "Creating automator with MODE=multi_user",
                    }
                )
                automator = BizBuySellAutomator(
                    network_utility=self.net, settings=self.settings
                )
                automator.init_driver()
                if self.settings["FILE_SOURCE"] == "google_drive":
                    # Download the CSV for multi-user execution
                    # should be formatted as username,password,csv_path where
                    # csv_path is the batch upload file for that user
                    multi_user_csv_path = (
                        automator.gdrive_client.download_file_from_google_drive(
                            shared_link=self.settings["MULTI_USER_CSV"],
                            temporary_filename="multi-user-tmp.csv",
                        )
                    )
                elif self.settings["FILE_SOURCE"] == "local":
                    # use the local FS path to the file; csv_path column should also specify local FS paths
                    # for each user
                    multi_user_csv_path = self.settings["MULTI_USER_CSV"]

                elif self.settings["FILE_SOURCE"] == "s3":
                    try:
                        # required variable is present
                        assert all(
                            x is not None
                            for x in [
                                self.settings["AWS_S3_BUCKET"],
                                self.settings["AWS_S3_REGION"],
                            ]
                        )
                    except AssertionError as e:
                        self.error(
                            {
                                "method": "Driver.run_lambda",
                                "message": "Missing AWS S3 environment variables for multi_user mode",
                                "error": str(e),
                            }
                        )
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
                            bucket_name=self.settings["AWS_S3_BUCKET"],
                            file_key=self.settings["MULTI_USER_CSV"],
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
                self.error(
                    {
                        "method": "Driver.run_lambda",
                        "message": "TimeoutException in multi_user mode",
                        "error": str(e),
                    }
                )
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": str(e), "ip": self.ip},
                }
            except Exception as e:
                self.error(
                    {
                        "method": "Driver.run_lambda",
                        "message": "Exception in multi_user mode",
                        "error": str(e),
                    }
                )
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": str(e), "ip": self.ip},
                }

    def handle_s3_trigger_single_user_mode(
        self, s3_bucket: str = "", s3_updated_file_key: str = ""
    ):
        """Run automation with MODE=single_user for user corresponding to the
        updated file in S3 that triggered execution.
        - pull creds for the updated file key from the CREDENTIALS_FILE (csv)
        - the lambda runs the single user mode execution with the S3 file as the CSV,
        and the username and password from CREDENTIALS_FILE as the creds
        Args:
        s3_bucket (str) - name of bucket where file was updated
        s3_updated_file_key (str) - key (location or path) of file updated
        """
        self.info(
            {
                "method": "Driver.handle_s3_trigger_single_user_mode",
                "args": {
                    "s3_bucket": s3_bucket,
                    "s3_updated_file_key": s3_updated_file_key,
                },
                "message": "Handling S3 trigger for single_user mode",
            }
        )
        self.settings["MODE"] = "single_user"
        try:
            self.info(
                {
                    "method": "Driver.handle_s3_trigger_single_user_mode",
                    "message": "Running single_user mode for file updated in S3",
                }
            )
            automator = BizBuySellAutomator(
                network_utility=self.net,
                settings=self.settings,
                s3_updated_file_key=s3_updated_file_key,
            )
            automator.init_driver()
            creds_for_file = automator.get_creds_for_csv_file(
                csv_file_path=s3_updated_file_key
            )
            assert creds_for_file is not None
            self.info(
                {
                    "method": "Driver.handle_s3_trigger_single_user_mode",
                    "message": f"Found creds for {s3_updated_file_key}; automating user session for user {creds_for_file['username']}",
                }
            )
            automator.automate_single_user_session(
                username=creds_for_file["username"],
                password=creds_for_file["password"],
                csv_path=s3_updated_file_key,
            )
            automator.quit()
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "success": (
                        f"batch upload of {s3_updated_file_key} complete"
                        f"for single_user {creds_for_file['username']}"
                    ),
                    "ip": self.ip,
                },
            }
        except TimeoutException as e:
            self.error(
                {
                    "method": "Driver.handle_s3_trigger_single_user_mode",
                    "message": "TimeoutException in single_user mode",
                    "error": str(e),
                }
            )
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": {"error": str(e), "ip": self.ip},
            }
        except Exception as e:
            self.error(
                {
                    "method": "Driver.handle_s3_trigger_single_user_mode",
                    "message": "Exception in single_user mode",
                    "error": str(e),
                }
            )
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": {"error": str(e), "ip": self.ip},
            }
