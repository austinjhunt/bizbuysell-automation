import os
import csv
import logging
import traceback
from time import sleep
from selenium import webdriver
from tempfile import mkdtemp
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from clients import GoogleDriveClient, S3Client
from log import BaseLogger
from net import NetworkUtility


class all_elements_satisfy(object):
    """
    Custom condition to use for verifying that all Selenium web
    elements match a certain condition
    """

    def __init__(self, locator, condition):
        self.locator = locator
        self.condition = condition

    def __call__(self, driver):
        elements = driver.find_elements(*self.locator)
        return all(self.condition(element) for element in elements)


class BizBuySellAutomator(BaseLogger):
    def __init__(self, network_utility: NetworkUtility = None, settings: dict = {}):
        """
        Initialize the automator to automate a BizBuySell.com upload session
        Args:
        network_utility (NetworkUtility) - instance of NetworkUtility passed from the
        driver for the purpose of reusing it across all instances of BizBuySellAutomator

        settings (dict) - settings parsed from a combination of a lambda event and
        the environment variables (with priority given to lambda event in cases where
        vars are defined in both places)
        """
        super().__init__(name="BizBuySellAutomator", settings=settings)
        self.net = network_utility
        if self.settings["FILE_SOURCE"] == "google_drive":
            self.gdrive_client = GoogleDriveClient(settings=self.settings)
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
                self.error(traceback.format_exc())
            self.s3_client = S3Client(settings=self.settings)

    def init_driver(self) -> None:
        """set self.driver to a Chrome driver using Selenium"""
        self.info("Creating Chrome driver")
        # Set up the ChromeDriver with the executable file paths
        chrome_binary_path = self.settings["CHROME_PATH"]
        webdriver_path = self.settings["CHROME_DRIVER_PATH"]
        self.debug(f"Chrome Binary Path: {chrome_binary_path}")
        self.debug(f"Chrome Driver Path: {webdriver_path}")
        options = webdriver.ChromeOptions()
        options.binary_location = chrome_binary_path
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--incognito")
        options.add_argument("--window-size=1280x1696")
        options.add_argument("--enable-javascript")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-dev-tools")
        options.add_argument("--no-zygote")
        options.add_argument(f"--user-data-dir={mkdtemp()}")
        options.add_argument(f"--data-path={mkdtemp()}")
        options.add_argument(f"--disk-cache-dir={mkdtemp()}")
        options.add_argument("--remote-debugging-port=9222")

        # Was getting Access Denied response. Add user agent to resolve.
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        options.add_argument(f"--user-agent={user_agent}")
        options.add_argument(
            "--lang=en-US,en;q=0.9"
        )  # Example: English (United States) and English with lower priority

        if self.settings["PRODUCTION"]:
            for prod_arg in [
                "--headless",
                "--single-process",
            ]:  # comment out the proxy temporarily #, f'--proxy-server={TOR_PROXIES["https"]}']:
                self.debug(f"Adding production arg {prod_arg} to Chrome driver")
                options.add_argument(prod_arg)

        # Initialize ChromeDriver instance
        self.driver = webdriver.Chrome(
            service=Service(executable_path=webdriver_path), options=options
        )

    def login(self, username: str = "", password: str = "") -> None:
        """Log a user into the web app given username and password

        Arguments:
        username (str) - user's username or email
        password (str) - user's password

        Very odd script on https://www.bizbuysell.com/users/login.aspx handling the login form functionality, pasting here for reference
        so reader is not confused about approach taken.

        $("#txtUserNamePlaceHolder").on('paste input',
            function () {
                $("#ctl00_ctl00_Content_ContentPlaceHolder1_LoginControl_txtUserName").val($("#txtUserNamePlaceHolder").val());
                $("#txtUserNamePlaceHolder").val("");
                $("#txtUserNameSection").removeClass("hidden");
                $("#txtUserNamePlaceHolder").addClass("hidden");
            });
        $("#ctl00_ctl00_Content_ContentPlaceHolder1_LoginControl_txtUserName").on('paste input',
            function () {
                $("#txtUserNameSection").removeClass("hidden");
                $("#txtUserNamePlaceHolder").addClass("hidden");
            });


        // same for password

        $("#txtPasswordPlaceHolder").on('paste input',
            function () {
                $("#ctl00_ctl00_Content_ContentPlaceHolder1_LoginControl_txtPassword").val($("#txtPasswordPlaceHolder").val());
                $("#txtPasswordPlaceHolder").val("");
                $("#txtPasswordSection").removeClass("hidden");
                $("#txtPasswordPlaceHolder").addClass("hidden");
            });
        $("#ctl00_ctl00_Content_ContentPlaceHolder1_LoginControl_txtPassword").on('paste input',
            function () {
                $("#txtPasswordSection").removeClass("hidden");
                $("#txtPasswordPlaceHolder").addClass("hidden");
            });


        Returns:
        None
        """
        login_url = "https://www.bizbuysell.com/users/login.aspx"
        self.driver.get(url=login_url)
        self.debug(f"Waiting for login form fields and button")
        WebDriverWait(self.driver, self.settings["WEBDRIVER_TIMEOUT_SECONDS"]).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "input"))
        )

        # Have to use JS to populate "placeholder" input field, then trigger an input event
        # to get the real input fields to populate before clicking button
        self.driver.execute_script(
            f'const inputEvent = new Event("input"); '
            f'document.getElementById("txtUserNamePlaceHolder").value = "{username}";'
            f'document.getElementById("txtUserNamePlaceHolder").dispatchEvent(inputEvent);'
            f'document.getElementById("txtPasswordPlaceHolder").value = "{password}";'
            f'document.getElementById("txtPasswordPlaceHolder").dispatchEvent(inputEvent);'
            f'document.getElementById("ctl00_ctl00_Content_ContentPlaceHolder1_LoginControl_BtnLogin").click();'
        )

        self._wait_for_login_completion()

    def _wait_for_login_completion(self) -> None:
        """
        Helper method to wait for the login process to
        complete; it is complete once a certain element shows up on the dashboard
        Arguments: None
        Returns: None
        """
        self.debug("Waiting for login completion (for dashboard to display)")
        dashboard_element = WebDriverWait(
            self.driver, self.settings["WEBDRIVER_TIMEOUT_SECONDS"]
        ).until(EC.presence_of_element_located((By.ID, "brokerHdrDashboard")))
        self.debug("Now logged in!")

    def automate_upload(self, csv_file_path: str = "") -> None:
        """
        Automate the full upload process for a user already logged in to the web app
        Arguments:
        csv_file_path (str) - path to local CSV to be uploaded for batch listing update
        Returns: Nonee
        """
        self.info("Beginning automated upload process")

        batch_upload_page_url = (
            "https://www.bizbuysell.com/brokers/batch/batchupload.aspx"
        )
        self.debug(f"Getting batch upload page {batch_upload_page_url}")
        self.driver.get(url=batch_upload_page_url)

        self.debug("Waiting for file input field")
        # These functions are defined in-line on the page and it
        # enables the submit / upload button below.
        file_input_id = "ctl00_ContentPlaceHolder1_AsyncFileUploadBulkCSV_ctl02"
        choose_file_button_class = "chooseFileButton"
        upload_button_id = "ctl00_ContentPlaceHolder1_btnUploadDocument"
        file_input = WebDriverWait(
            self.driver, self.settings["WEBDRIVER_TIMEOUT_SECONDS"]
        ).until(EC.presence_of_element_located((By.ID, file_input_id)))
        self.debug(f"Sending CSV file path {csv_file_path} into input field")
        file_input.send_keys(csv_file_path)
        sleep(2)
        self.debug("Enabling and clicking Upload File button")
        self.driver.execute_script(f"AsyncFileUpload_ClientUploadComplete();")
        sleep(2)
        upload_button = WebDriverWait(
            self.driver, self.settings["WEBDRIVER_TIMEOUT_SECONDS"]
        ).until(EC.element_to_be_clickable((By.ID, upload_button_id)))
        upload_button.click()
        self.debug("Waiting for batchimport.aspx page to load")
        WebDriverWait(
            self.driver, self.settings["WEBDRIVER_UPLOAD_TIMEOUT_SECONDS"]
        ).until(EC.url_contains("batchimport.aspx"))

        # This brings you to a "Please confirm new listings to import
        # and existing listings to update." page. Assuming updateAll is the course of action.
        # Timeout should be extended a bit for file uploads
        update_all_button = WebDriverWait(
            self.driver, self.settings["WEBDRIVER_UPLOAD_TIMEOUT_SECONDS"]
        ).until(EC.presence_of_element_located((By.ID, "updateAll")))
        self.info("Clicking Update All button")
        update_all_button.click()

        self._wait_for_update_all_completion()

        # If there is also an Import Listings button, click that as well
        # (to handle new listings)
        try:
            import_all_button = self.driver.find_element(by=By.ID, value="importAll")
            self._prepare_all_new_imports()
            self.info("Clicking Import All")
            import_all_button.click()
            self._wait_for_import_all_completion()
        except NoSuchElementException as e:
            pass

    def _prepare_all_new_imports(self) -> None:
        """Before clicking Import All, the new records need to
        be prepped; each new record to be imported in the UI has
        two dropdowns. The first has a default value of "Established business"
        which is good, that is the default desired by the client.
        The second dropdown does not have a default value so we need to
        select "Miscellaneous Restaurant and Bar" for all records to keep things simple
        Args: None
        Returns: None
        """
        self.info("Preparing new imports with default Business Type")
        rows_to_be_imported = self.driver.find_elements(
            by=By.CSS_SELECTOR,
            value="#batchListingImports .batchRow",
        )
        for row in rows_to_be_imported:
            # there are two dropdowns
            # with same class and no usable ID. get the second dropdown
            # which is for Business Type
            dropdowns = row.find_elements(
                by=By.CSS_SELECTOR,
                value=".row .listingActions.menus.actions .dropdown.lActions",
            )
            if len(dropdowns) >= 2:
                business_type_dropdown = dropdowns[1]
                dropdown_toggle = WebDriverWait(
                    self.driver, timeout=self.settings["WEBDRIVER_TIMEOUT_SECONDS"]
                ).until(
                    EC.element_to_be_clickable(
                        business_type_dropdown.find_element(
                            by=By.CSS_SELECTOR,
                            value="a.current.btn.btn-secondary.dropdown-toggle",
                        )
                    )
                )
                dropdown_toggle.click()

                # now choose the option containing text Miscellaneous Restaurant and Bar
                business_type_dropdown_menu = business_type_dropdown.find_element(
                    by=By.CSS_SELECTOR, value="ul.dropdown-menu"
                )
                WebDriverWait(
                    self.driver, self.settings["WEBDRIVER_TIMEOUT_SECONDS"]
                ).until(
                    EC.element_to_be_clickable(
                        business_type_dropdown_menu.find_element(
                            by=By.XPATH,
                            value='li/a[contains(text(), "Miscellaneous Restaurant and Bar")]',
                        )
                    )
                ).click()

        self.info("All imports are prepared with default business type")

    def _wait_for_import_all_completion(self) -> None:
        """
        After clicking Update N Listing(s) button, wait for all listing
        records that need updating to update. They should all have the word complete
        in their status column.
        """
        self.info("Waiting for completion of Import Listings operation")
        wait = WebDriverWait(
            self.driver, self.settings["WEBDRIVER_UPLOAD_TIMEOUT_SECONDS"]
        )
        wait.until(
            all_elements_satisfy(
                locator=(
                    By.CSS_SELECTOR,
                    "#batchListingImports div.batchRow div.row.importItem div.col-sm-3",
                ),
                condition=lambda element: "complete" in element.text,
            )
        )
        self.info("Import All operation complete!")

    def _wait_for_update_all_completion(self) -> None:
        """
        After clicking Update N Listing(s) button, wait for all listing
        records that need updating to update. They should all have the word complete
        in their status column.
        """
        self.info("Waiting for completion of Update Listings operation")
        wait = WebDriverWait(
            self.driver, self.settings["WEBDRIVER_UPLOAD_TIMEOUT_SECONDS"]
        )
        wait.until(
            all_elements_satisfy(
                locator=(
                    By.CSS_SELECTOR,
                    "#batchListingUpdates div.updateRow div.row.updateItem div.col-sm-3",
                ),
                condition=lambda element: "complete" in element.text,
            )
        )
        self.info("Update All operation complete!")

    def _convert_shared_google_drive_link_to_downloadable_link(
        self, shared_link: str
    ) -> str:
        """When you copy a link to a Google Drive file, it is not a "downloadable" link, it
        is a view link. You can generate a downloadable link using the ID from the shared link.
        Arguments:
        shared_link (str) - link copied with "Copy Link" feature in Google Drive
        Returns:
        downloadable_link (str) - link that you can download using requests.get()
        """
        self.info(f"Converting shared link to downloadable link")
        drive_file_id = shared_link.split("https://drive.google.com/file/d/")[1].split(
            "/"
        )[0]
        downloadable_link = (
            f"https://drive.google.com/u/0/uc?id={drive_file_id}&export=download"
        )
        self.debug(f"Converted {shared_link} to downloadable link {downloadable_link}")
        return downloadable_link

    def get_creds_for_csv_file(self, csv_file_path: str):
        """
        Pull the credentials for the provided file path
        Arguments:
        csv_file_path (str) - could be a local file path, an S3 file key, or a Google file link
        Returns:
        creds (dict) - {"username": <username>, "password": <password>}
        """
        self.info(
            f"Pulling credentials for {csv_file_path} from {self.settings['CREDENTIALS_FILE']}"
        )
        creds_file_path = self.s3_client.download_file_from_s3_bucket(
            bucket_name=self.settings["AWS_S3_BUCKET"],
            file_key=self.settings["CREDENTIALS_FILE"],
            temporary_filename="s3tmpcredsfile.csv",
        )

        with open(creds_file_path, "r") as f:
            reader = csv.DictReader(f)
            data = {}
            for line in reader:
                filename = line["File Name"].strip()
                # csv_file_path could have a prefix if inside folder
                # so don't use ==
                if filename in csv_file_path:
                    username = line["Email"]
                    password = line["Password"]
                    self.info(f"Credentials found!")
                    return {"username": line["Email"], "password": line["Password"]}
        self.error("Credentials not found")
        return None

    def automate_single_user_session(
        self,
        username: str,
        password: str,
        csv_path: str,
    ) -> None:
        """Automates batch upload session for a single user
        Args:
        username (str) - user's username or email address
        password (str) - user's password
        csv_path (str) - csv corresponding to this user (to batch upload); this can be:
            1) a Google Drive CSV link if FILE_SOURCE=google_drive
            2) a local path if FILE_SOURCE=local
            3) a key (name of a file) in an S3 bucket if FILE_SOURCE=s3 (can be just the name if stored in bucket's root)

        Returns: None
        """
        self.info(f"Automating user session for {username}")

        self.login(username=username, password=password)

        if self.settings["FILE_SOURCE"] == "google_drive":
            # file not already on file system
            # Download the CSV for this user with the URL from the Lambda environment
            csv_file_path = self.gdrive_client.download_file_from_google_drive(
                shared_link=csv_path
            )
        elif self.settings["FILE_SOURCE"] == "local":
            # Already stored locally. Ensure path exists before using.
            self.debug(f"Asserting path existence before continuing: {csv_path}")
            assert os.path.exists(csv_path)
            csv_file_path = csv_path
        elif self.settings["FILE_SOURCE"] == "s3":
            csv_file_path = self.s3_client.download_file_from_s3_bucket(
                bucket_name=self.settings["AWS_S3_BUCKET"],
                file_key=csv_path,
                temporary_filename="s3tmpfile.csv",
            )

        # Automate the upload of that CSV on local path with
        # the current user's web app session
        self.automate_upload(csv_file_path=csv_file_path)

        # IF the file was downloaded from cloud, remove the temporary downloaded file
        if self.settings["FILE_SOURCE"] in ("google_drive", "s3"):
            os.remove(csv_file_path)

        self.logout()

    def automate_multiple_user_sessions(self, csv_file_path: str = "") -> None:
        self.info("Automating multiple user batch upload sessions")
        with open(csv_file_path, "r") as f:
            reader = csv.DictReader(f)
            for user_row in reader:
                self.automate_single_user_session(
                    username=user_row["username"],
                    password=user_row["password"],
                    csv_path=user_row["csv_path"],
                )

    def logout(self) -> None:
        """Log user out of web app"""
        # Get the sign out button from the collapsible
        # menu in the navigation with a CSS selector
        chain = ActionChains(self.driver, duration=2000)
        topright_dropdown_button = WebDriverWait(
            self.driver, self.settings["WEBDRIVER_TIMEOUT_SECONDS"]
        ).until(EC.element_to_be_clickable((By.ID, "dropMyBBS")))
        topright_dropdown_button.click()
        signout_button = WebDriverWait(
            self.driver, self.settings["WEBDRIVER_TIMEOUT_SECONDS"]
        ).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "li#topNav_MyBBS ul.dropdown-menu li:last-child a")
            )
        )
        signout_button.click()
        WebDriverWait(self.driver, self.settings["WEBDRIVER_TIMEOUT_SECONDS"]).until(
            EC.presence_of_element_located((By.ID, "hlSignIn"))
        )
        self.info("Logged out! Sign in button is present.")

    def quit(self) -> None:
        """Log the user out of the web app and quit
        the Selenium automation web driver session
        Arguments: None
        Returns: None
        """
        self.info("Shutting down")

        self.driver.close()
        self.driver.quit()
