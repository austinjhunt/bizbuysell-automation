import os 
import requests  
from config import TEMP_FOLDER


class S3Client: 
    def __init__(self): 
        pass 
class GoogleDriveClient:
    """Utility class for downloading Google Drive files; methods provided by turdus-merula on https://stackoverflow.com/questions/38511444/python-download-files-from-google-drive-using-url
    """

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
        Returns:
        destination (str) - local path to downloaded file
        """

        if not temporary_filename:
            temporary_filename = "tmp.csv"
        destination = os.path.join(TEMP_FOLDER, temporary_filename)
        session = requests.Session()
        id = self.get_google_drive_file_id_from_shared_link(shared_link=shared_link)
        url = f"https://docs.google.com/uc?id={id}&confirm=1&export=download"
        response = session.get(url, stream=True)
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
