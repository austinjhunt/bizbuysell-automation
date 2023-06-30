# BizBuySell Automator

This is a project completed for an UpWork freelance job (for client Robin Gagnon and [Connor Thomson](mailto:connor@wesellrestaurants.com)). The project leverages Selenium and Python to automate the batch uploading of business listings in CSV format to [BizBuySell](https://bizbuysell.com), the Internet's largest business for sale exchange.

# Problem Statement from UpWork Job

**Sunday, June 25th: Robin Gagnon sent an offer.**
I need a script that will mimic the steps we take to log into a website with the user credentials and do a batch upload of a .csv file and then log out.

I will need to duplicate this process 30 times for 30 different user accounts so in addition to the script I need the ability to know where to edit the script to substitute:

1. Different user name and login credentials
2. Different location for the source file

I have an example video I can send to qualified candidates showing all the steps which are:

Step 1: Go to a URL and click Login
Step 2: Login in with user name and password
Step 3: Choose "My Listings" and batch listing upload
Step 4: Click "Upload file"
Step 5: Choose File from Source Destination provided
Step 6: Click to confirm upload
Step 7: Sign out

## Approach

I completed the project after approximately 16 hours of work. The main obstacle was not development with Selenium, but was finding the proper web driver and browser binaries that would be compatible with the AWS Lambda environment. I started out as most do, intending to just build out the project locally, test it, then zip the whole thing up (with the Python packages, the web driver, and the Chrome binary) and upload the zip file to AWS Lambda to create a new function. Nope. Size limitations of Lambda ultimately led me to use [a Docker image from umihico on GitHub](https://github.com/umihico/docker-selenium-lambda/tree/main) since the use of container images comes with a much more lenient size requirement. This approach allows execution of the function without having to use S3 for separate storage of large binaries or separate layers in Lambda to split up the project into size-limited chunks. Instead, I could now just build the whole project with its dependencies into a single Docker image (`docker build -t bizbuysellautomator .`) and deploy it to Elastic Container Registry. Moreover, one can also run it outside of AWS entirely on any machine with Docker installed. The [umihico Docker image](https://github.com/umihico/docker-selenium-lambda/tree/main) has the latest Chrome web driver and browser built in so no need to go searching for and downloading those (large) files unless you want to do further development and testing outside of the Docker image from umihico.

## Project Details

The project does precisely what the problem statement asks for, with some additions to account for different potential use cases.

### Additions to Base Automation Request

The primary function (formatted as a Lambda Handler) takes in an event that contains all the driving arguments determining how the automation will run. To ensure that the client does not need to go in and change the source and redeploy every time they are running a different batch upload for a different user, I made the function accept parameters defining a mode to run in, with each mode offering its own corresponding parameters. Below are two examples, one for a "Single User Batch Upload" mode and one for a "Multi User Batch Upload Mode":

```
   single_user_sample_event = {
        "mode": "single_user",
        "verbose": True,
        "single_user_username": "****",
        "single_user_password": "****",
        "single_user_google_drive_csv_link": "https://drive.google.com/file/d/SOME_LONG_FILE_ID_HERE/view?usp=drive_link",
    }
```

In **single_user mode**, the batch upload automation is only going to be run for the **one user** whose creds are specified in the payload. The single_user parameters are both prefixed with single_user and they are all required. The creds allow the login to [BizBuySell](https://bizbuysell.com) with Selenium, and the CSV file link is consumed as a Google Drive link configured with an "Anyone with the link can view" setting from Google Drive. That CSV (`single_user_google_drive_csv_link`) needs to be present and should link to the batch upload CSV file for this user. The function will download the CSV as a temporary file, then upload that temporary file with the Batch Upload feature on BizBuySell using Selenium.

```
    multi_user_sample_event = {
         "mode": "multi_user",
         "verbose": True,
         "multi_user_google_drive_csv_link": "https://drive.google.com/file/d/13r6kV-7rf6yfyeRIFUo-neRk8viXBuAV/view?usp=drive_link",
    }

```

**multi_user mode** is essentially just a wrapper around the single user mode in the form of a loop. In this case, though, there are no creds passed in the payload; there is just a `multi_user_csv_google_drive_link` whose value links to a CSV formatted as `username,password,csv_link`. Each record in that "multi user CSV" file should have a username and password to log in to BizBuySell with, and a Google Drive link to a batch upload CSV corresponding to that user.
The following is what ultimately gets executed after `multi_user_csv_google_drive_link` gets downloaded to `csv_file_path`:

```
def automate_multiple_user_sessions(self, csv_file_path: str = "") -> None:
        self.info("Automating multiple user batch upload sessions")
        with open(csv_file_path, "r") as f:
            reader = csv.DictReader(f)
            for user_row in reader:
                self.automate_single_user_session(
                    username=user_row["username"],
                    password=user_row["password"],
                    csv_link=user_row["csv_link"],
                )
```

Moreover, after correspondence with Connor over email about the details of the upload process, the function is now able to fully handle both the **update of existing business listing records** as well as the **import of new business listing records** with default values selected for listing type and business type on new imports, which will help to reduce the amount of manual work that needs to be done after the automation completes.

WeSellRestaurantsGithub
