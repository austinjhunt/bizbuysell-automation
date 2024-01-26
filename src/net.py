""" Module responsible for changing IP address for the production environment
by leveraging NAT gateways and Elastic IP assignment to an AWS Function within
the context of that AWS function """

import requests
import traceback
from log import BaseLogger


class NetworkUtility(BaseLogger):
    def __init__(self, settings: dict = {}):
        """
        Args:
        settings (dict) - settings parsed from a combination of a lambda event and
        the environment variables (with priority given to lambda event in cases where
        vars are defined in both places)
        """
        super().__init__(name="NetUtil", settings=settings)
        self.info(
            {
                "method": "NetworkUtility.__init__",
                "args": {"settings": "***"},
                "message": "Initializing NetworkUtility",
            }
        )

    def get_public_ip(self):
        """Pull the public IP address of the device running this program
        Args: none
        Returns:
        ip (str) - public IP address of this device
        """
        self.info(
            {
                "method": "get_public_ip",
                "args": {},
                "message": "Getting public IP address",
            }
        )
        try:
            response = requests.get("https://api64.ipify.org?format=json", timeout=3)
            ip = response.json().get("ip")
            self.info(
                {
                    "method": "get_public_ip",
                    "args": {},
                    "message": f"Got public IP address: {ip}",
                }
            )
            return ip
        except requests.exceptions.Timeout:
            self.error(traceback.format_exc())
            return None
        except requests.RequestException:
            self.error(traceback.format_exc())
            return None

    # make printable
    def __str__(self):
        return f"NetworkUtility"
