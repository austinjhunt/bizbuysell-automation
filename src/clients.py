import os
import requests
import boto3
from config import TEMP_FOLDER, AWS_S3_REGION, WEBDRIVER_TIMEOUT_SECONDS
from log import BaseLogger


class S3Client(BaseLogger):
    """Client for reading files from AWS S3"""

    def __init__(self):
        super().__init__(name="S3Client")
        self.session = boto3.Session(
            aws_access_key_id="<your_access_key_id>",
            aws_secret_access_key="<your_secret_access_key>",
        )

        self.s3 = boto3.client("s3", region_name=AWS_S3_REGION)

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
        self.info(f"Getting files from S3 (bucket={bucket_name})")
        response = self.s3.list_objects_v2(Bucket=bucket_name)
        self.debug("Response from s3.list_objects_v2: ")
        self.debug(response)
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
            f"Downloading file from S3 (Key={file_key}, Bucket={bucket_name},"
            f"temporary_filename={temporary_filename})"
        )
        if not temporary_filename:
            temporary_filename = "tmp.csv"
        destination = os.path.join(TEMP_FOLDER, temporary_filename)
        self.s3.download_file(Bucket=bucket_name, Key=file_key, Filename=destination)
        return destination


class GoogleDriveClient(BaseLogger):
    """Client for downloading Google Drive files; methods provided by
    turdus-merula on https://stackoverflow.com/questions/38511444/python-download-files-from-google-drive-using-url
    """

    def __init__(self):
        super().__init__(name="S3Client")

    def get_google_drive_file_id_from_shared_link(self, shared_link: str) -> str:
        """
        shared_link (str) - link copied with "Copy Link" feature in Google Drive
        Returns:
        file_id (str) - ID of the Google Drive file
        """
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
            f"Downloading file from Google Drive (link={shared_link},"
            f"temporary_filename={temporary_filename})"
        )
        if not temporary_filename:
            temporary_filename = "tmp.csv"
        destination = os.path.join(TEMP_FOLDER, temporary_filename)
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

        with open(destination, "wb") as f:
            for chunk in response.iter_content(CHUNK_SIZE):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)