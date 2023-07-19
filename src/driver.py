import logging
import os
import traceback
import logging
import os
import logging
from selenium.common.exceptions import TimeoutException
from config import *
from bizbuysell import BizBuySellAutomator


class Driver:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.setup_logging()

    def setup_logging(self, name: str = "Driver") -> None:
        """set up self.logger for Driver logging
        Args:
        name (str) - what this object should be called, will be used as logging prefix
        """
        self.name = name
        self.logger = logging.getLogger(self.name)
        self.logger.propagate = False
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        format = "[%(prefix)s - %(filename)s:%(lineno)s - %(funcName)3s() ] %(message)s"
        formatter = logging.Formatter(format)
        handlerStream = logging.StreamHandler()
        handlerStream.setFormatter(formatter)
        self.logger.addHandler(handlerStream)
        level = logging.DEBUG if self.verbose else logging.INFO
        self.logger.setLevel(level)

    def debug(self, msg) -> None:
        self.logger.debug(msg, extra={"prefix": self.name})

    def info(self, msg) -> None:
        self.logger.info(msg, extra={"prefix": self.name})

    def error(self, msg) -> None:
        self.logger.error(msg, extra={"prefix": self.name})

    def run_local(self) -> None:
        """Method to run the automation on a local server without AWS lambda.
        Uses environment variables instead of lambda event to drive execution"""
        self.info("Running local execution with values from environment variables")
        mode = MODE  # alt = multi_user
        if mode == "single_user":
            try:
                # required variables are present
                assert all(x != "" for x in [
                           SINGLE_USER_PASSWORD, 
                           SINGLE_USER_USERNAME, 
                           SINGLE_USER_CSV])
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
                        )
                    },
                }
            self.info("Creating automator with MODE=single_user")
            try:
                automator = BizBuySellAutomator(verbose=self.verbose)
                automator.init_driver()
                automator.automate_single_user_session(
                    username=SINGLE_USER_USERNAME,
                    password=SINGLE_USER_PASSWORD,
                    csv_link=SINGLE_USER_CSV
                )
                automator.quit()
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "success": (
                            f'batch upload of {SINGLE_USER_CSV}'
                            f' complete for single_user {SINGLE_USER_USERNAME}'
                        )
                    },
                }
            except TimeoutException as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc()},
                }
            except Exception as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc()},
                }

        elif mode == "multi_user":
            try:
                # required variable is present 
                assert MULTI_USER_CSV != ""
            except AssertionError as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "error": (
                            "must provide MULTI_USER_CSV as environment variable "
                            "for multi_user mode - csv should include "
                            "username,password,csv_link as columns"
                        )
                    },
                }
            try:
                self.info("Creating automator with mode=multi_user")
                automator = BizBuySellAutomator(verbose=self.verbose)
                automator.init_driver()
                if FILE_SOURCE == "google_drive":
                    # Download the CSV for multi-user execution
                    # should be formatted as username,password,csv_link where
                    # csv_link is the batch upload file for that user
                    multi_user_csv_path = automator.gdrive_client.download_file_from_google_drive(
                        shared_link=MULTI_USER_CSV,
                        temporary_filename="multi-user-tmp.csv",
                    )
                elif FILE_SOURCE == "local":
                    # use the local FS path to the file; csv_link column should also specify local FS paths
                    # for each user
                    multi_user_csv_path = MULTI_USER_CSV
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
                    "body": {"error": traceback.format_exc()},
                }
            except Exception as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc()},
                }

    def run_lambda(self, event, context) -> None:
        """Run automation with AWS lambda using event to drive execution"""
        self.info("Running AWS Lambda execution with values from event")
        if "mode" not in event or event["mode"] == "single_user":
            try:
                assert all(
                    x in event
                    for x in [
                        "single_user_password",
                        "single_user_username",
                        "single_user_csv",
                    ]
                )
            except AssertionError as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "error": (
                            "must provide single_user_password, "
                            "single_user_username, and single_user_csv "
                            "in body for single_user mode"
                        )
                    },
                }
            self.info("Creating automator with mode=single_user")
            try:
                automator = BizBuySellAutomator(verbose=self.verbose)
                automator.init_driver()
                automator.automate_single_user_session(
                    username=event["single_user_username"],
                    password=event["single_user_password"],
                    csv_link=event["single_user_csv"],
                )
                automator.quit()
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "success": (
                            f'batch upload of {event["single_user_csv"]}'
                            f" complete for single_user {event['single_user_username']}"
                        )
                    },
                }
            except TimeoutException as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc()},
                }
            except Exception as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc()},
                }

        elif event["mode"] == "multi_user":
            try:
                assert "multi_user_csv" in event
            except AssertionError as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {
                        "error": (
                            "must provide multi_user_csv in body "
                            "for multi_user_mode - csv should include "
                            "username,password,csv_link as columns"
                        )
                    },
                }
            try:
                self.info("Creating automator with mode=multi_user")
                automator = BizBuySellAutomator(verbose=self.verbose)
                automator.init_driver()
                # Download the CSV for multi-user execution
                # should be formatted as username,password,csv_link where
                # csv_link is the batch upload file for that user
                multi_user_csv_path = (
                    automator.gdrive_client.download_file_from_google_drive(
                        shared_link=event["multi_user_csv"],
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
                    "body": {"error": traceback.format_exc()},
                }
            except Exception as e:
                self.error(traceback.format_exc())
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": traceback.format_exc()},
                }
