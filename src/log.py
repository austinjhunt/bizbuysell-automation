import io
import logging
import boto3
from config import VERBOSE

""" Parent class inherited by other classes for handling logging """


class BaseLogger:
    def __init__(self, name: str = ""):
        self.name = name
        self.setup_logging()

    def setup_logging(self) -> None:
        """set up self.logger for Driver logging
        Args:
        name (str) - what this object should be called, will be used as logging prefix
        """
        self.logger = logging.getLogger(self.name)
        self.logger.propagate = False
        level = logging.DEBUG if VERBOSE else logging.INFO
        self.logger.setLevel(level)

        if self.logger.hasHandlers():
            self.logger.handlers.clear()
        format = "[%(prefix)s - %(filename)s:%(lineno)s - %(funcName)3s() ] %(message)s"
        formatter = logging.Formatter(format)
        # Normal logging. Will show up in console or docker logs or
        # in AWS Cloudtrail logs if running in AWS.
        handlerStream = logging.StreamHandler()
        handlerStream.setFormatter(formatter)
        self.logger.addHandler(handlerStream)

    def debug(self, msg) -> None:
        self.logger.debug(msg, extra={"prefix": self.name})

    def info(self, msg) -> None:
        self.logger.info(msg, extra={"prefix": self.name})

    def error(self, msg) -> None:
        self.logger.error(msg, extra={"prefix": self.name})
