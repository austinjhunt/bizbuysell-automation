import os
import requests
import boto3
from log import BaseLogger


class S3Client(BaseLogger):
    """Client for reading files from AWS S3"""

    def __init__(self, settings: dict = {}, s3_updated_file_key: str = ""):
        """
        Args:
        settings (dict) - settings parsed from a combination of a lambda event and
        the environment variables (with priority given to lambda event in cases where
        vars are defined in both places)
        """
        super().__init__(name="S3Client", settings=settings)
        self.s3_updated_file_key = s3_updated_file_key
        self.info(
            {
                "method": "S3Client.__init__",
                "args": {
                    "settings": "***",
                    "s3_updated_file_key": self.s3_updated_file_key,
                },
                "message": "Initializing S3Client",
            }
        )
        if self.settings["ENV"] == "local":
            # permissions come from passed credentials
            self.s3 = boto3.client(
                "s3",
                region_name=self.settings["AWS_S3_REGION"],
                aws_access_key_id=self.settings["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=self.settings["AWS_SECRET_ACCESS_KEY"],
            )
        elif self.settings["ENV"] == "lambda":
            # permissions come from execution role
            self.s3 = boto3.client("s3", region_name=self.settings["AWS_S3_REGION"])

    def get_file_metadata(self, bucket_name: str = "", file_key: str = ""):
        """Return an S3 file's metadata given its parent bucket and its key (location in the bucket)"""
        self.info(
            {
                "method": "get_file_metadata",
                "args": {"bucket_name": bucket_name, "file_key": file_key},
                "message": "Getting file metadata from S3",
                "file_key": self.s3_updated_file_key,
            }
        )
        res = self.s3.head_object(Bucket=bucket_name, Key=file_key)
        if "Metadata" in res:
            return res["Metadata"]
        return None

    def get_all_files_from_s3_bucket(self, bucket_name: str = ""):
        """
            Return list of files stored in specified AWS S3 Bucket

            Args:
            bucket_name (str) - name of the S3 bucket to list files for
            Returns:
            files_in_bucket (list) - list of files stored in bucket, in the following format:
            [
            {
                'Key': 'string',
                'LastModified': datetime(2015, 1, 1),
                'ETag': 'string',
                'ChecksumAlgorithm': [
                    'CRC32'|'CRC32C'|'SHA1'|'SHA256',
                ],
                'Size': 123,
                'StorageClass': 'STANDARD'|'REDUCED_REDUNDANCY'|'GLACIER'|'STANDARD_IA'|'ONEZONE_IA'|'INTELLIGENT_TIERING'|'DEEP_ARCHIVE'|'OUTPOSTS'|'GLACIER_IR'|'SNOW',
                'Owner': {
                    'DisplayName': 'string',
                    'ID': 'string'
                },
                'RestoreStatus': {
                    'IsRestoreInProgress': True|False,
                    'RestoreExpiryDate': datetime(2015, 1, 1)
                }
            },
            ...
        ],
        """
        self.info(
            {
                "method": "get_all_files_from_s3_bucket",
                "args": {"bucket_name": bucket_name},
                "message": "Getting all files from S3 bucket",
                "file_key": self.s3_updated_file_key,
            }
        )
        response = self.s3.list_objects_v2(Bucket=bucket_name)
        self.debug(
            {
                "method": "get_all_files_from_s3_bucket",
                "message": "Response from S3",
                "response": response,
                "file_key": self.s3_updated_file_key,
            }
        )
        files_in_bucket = response["Contents"]
        return files_in_bucket

    def download_file_from_s3_bucket(
        self, bucket_name: str = "", file_key: str = "", temporary_filename: str = ""
    ):
        """Download a file given its key (its path from the bucket root) in AWS_S3_BUCKET
        Args:
        bucket_name (str) - name of the AWS S3 bucket from which file should be downladed
        file_key (str) - key for the file to be downloaded, obtained from the "Key" attribute of the
            file from the Bucket Contents returned from get_all_files_from_s3_bucket
        temporary_filename (str) - optional name of local file to which content should be downloaded
            (this will be removed from local file system after processing)

        Returns:
        destination (str) - local path to downloaded file
        """
        self.info(
            {
                "method": "download_file_from_s3_bucket",
                "args": {
                    "bucket_name": bucket_name,
                    "file_key": file_key,
                    "temporary_filename": temporary_filename,
                },
                "message": "Downloading file from S3",
                "file_key": self.s3_updated_file_key,
            }
        )
        if not temporary_filename:
            temporary_filename = "tmp.csv"
        destination = os.path.join(self.settings["TEMP_FOLDER"], temporary_filename)
        self.s3.download_file(Bucket=bucket_name, Key=file_key, Filename=destination)
        return destination


class GoogleDriveClient(BaseLogger):
    """Client for downloading Google Drive files; methods provided by
    turdus-merula on https://stackoverflow.com/questions/38511444/python-download-files-from-google-drive-using-url
    """

    def __init__(self, settings: dict = {}):
        """
        Args:
        settings (dict) - settings parsed from a combination of a lambda event and
        the environment variables (with priority given to lambda event in cases where
        vars are defined in both places)
        """
        self.info(
            {
                "method": "GoogleDriveClient.__init__",
                "args": {"settings": "***"},
                "message": "Initializing GoogleDriveClient",
            }
        )
        super().__init__(name="S3Client", settings=settings)

    def get_google_drive_file_id_from_shared_link(self, shared_link: str) -> str:
        """
        shared_link (str) - link copied with "Copy Link" feature in Google Drive
        Returns:
        file_id (str) - ID of the Google Drive file
        """
        self.info(
            {
                "method": "get_google_drive_file_id_from_shared_link",
                "args": {"shared_link": shared_link},
                "message": "Getting Google Drive file ID from shared link",
            }
        )
        return shared_link.split("https://drive.google.com/file/d/")[1].split("/")[0]

    def download_file_from_google_drive(
        self, shared_link: str = "", temporary_filename: str = ""
    ) -> str:
        """Download a file from Google Drive without SDK, just with file ID
        Args:
        id (str) - id of file on google drive
        temporary_filename (str) - optional name of local file to which content should be written
            (this will be removed from local file system after processing)
        Returns:
        destination (str) - local path to downloaded file
        """
        self.info(
            {
                "method": "download_file_from_google_drive",
                "args": {
                    "shared_link": shared_link,
                    "temporary_filename": temporary_filename,
                },
                "message": "Downloading file from Google Drive",
            }
        )
        if not temporary_filename:
            temporary_filename = "tmp.csv"
        destination = os.path.join(self.settings["TEMP_FOLDER"], temporary_filename)
        session = requests.Session()
        id = self.get_google_drive_file_id_from_shared_link(shared_link=shared_link)
        url = f"https://docs.google.com/uc?id={id}&confirm=1&export=download"
        response = session.get(url, stream=True, timeout=3)
        self.save_response_content(response, destination)
        return destination

    def save_response_content(
        self, response: requests.Response, destination: str = ""
    ) -> None:
        """Save response content (file download) in chunks
        args:
        response (requests.Response) - file download response
        destination (str) - path to local file to which content should be written"""
        CHUNK_SIZE = 32768
        self.info(
            {
                "method": "save_response_content",
                "args": {"destination": destination},
                "message": f"Saving response content with chunk size {CHUNK_SIZE}",
            }
        )
        with open(destination, "wb") as f:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
