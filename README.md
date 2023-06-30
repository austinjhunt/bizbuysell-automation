# BizBuySell Automator

This is a project completed for an UpWork freelance job (for client Robin Gagnon and [Connor Thompson](mailto:connor@wesellrestaurants.com)). The project leverages Selenium and Python to automate the batch uploading of business listings in CSV format to [BizBuySell](https://bizbuysell.com), the Internet's largest business for sale exchange.

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

I completed the project after approximately 21 hours of work. The main obstacle was not development with Selenium, but was finding the proper web driver and browser binaries that would be compatible with the AWS Lambda environment. I started out as most do, intending to just build out the project locally, test it, then zip the whole thing up (with the Python packages, the web driver, and the Chrome binary) and upload the zip file to AWS Lambda to create a new function. Nope. Size limitations of Lambda ultimately led me to use [a Docker image from umihico on GitHub](https://github.com/umihico/docker-selenium-lambda/tree/main) since the use of container images comes with a much more lenient size requirement. This approach allows execution of the function without having to use S3 for separate storage of large binaries or separate layers in Lambda to split up the project into size-limited chunks. Instead, I could now just build the whole project with its dependencies into a single Docker image (`docker build -t bizbuysellautomator .`) and deploy it to Elastic Container Registry. Moreover, one can also run it outside of AWS entirely on any machine with Docker installed. The [umihico Docker image](https://github.com/umihico/docker-selenium-lambda/tree/main) has the latest Chrome web driver and browser built in so no need to go searching for and downloading those (large) files unless you want to do further development and testing outside of the Docker image from umihico.

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
        "multi_user_csv": "https://drive.google.com/file/d/SOME_LONG_FILE_ID_HERE/view?usp=drive_link",
    }
```

In **single_user mode**, the batch upload automation is only going to be run for the **one user** whose creds are specified in the payload. The single_user parameters are both prefixed with single_user and they are all required. The creds allow the login to [BizBuySell](https://bizbuysell.com) with Selenium, and the CSV file link is consumed as a Google Drive link configured with an "Anyone with the link can view" setting from Google Drive. That CSV (`multi_user_csv`) needs to be present and should link to the batch upload CSV file for this user. The function will download the CSV as a temporary file, then upload that temporary file with the Batch Upload feature on BizBuySell using Selenium.

```
    multi_user_sample_event = {
         "mode": "multi_user",
         "verbose": True,
         "multi_user_csv": "https://drive.google.com/file/d/SOME_LONG_FILE_ID_HERE/view?usp=drive_link",
    }

```

**multi_user mode** is essentially just a wrapper around the single user mode in the form of a loop. In this case, though, there are no creds passed in the payload; there is just a `multi_user_csv` whose value links to a CSV formatted as `username,password,csv_link`. Each record in that "multi user CSV" file should have a username and password to log in to BizBuySell with, and a Google Drive link to a batch upload CSV corresponding to that user.
The following is what ultimately gets executed after `multi_user_csv` gets downloaded to `csv_file_path`:

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

## File Sources - Important

When running with AWS Lambda, CSV files are not specified as file system paths, but are instead specified with Google Drive links. That is the only option for AWS Lambda execution. Upload the CSV to Google Drive, right click, Share, and use the "Anyone with the link can view" setting. Then, copy the link and provide that as the value for the single/multi_user_csv parameter. If you are using multi user mode, the CSVs referenced for each user in the multi user CSV (where columns are username,password,csv_link) also need to be Google Drive links with the same "Anyone with the link can view" permission. Taking the previous multi_user example:

```

    multi_user_sample_event = {
         "mode": "multi_user",
         "verbose": True,
         "multi_user_csv": "https://drive.google.com/file/d/SOME_LONG_FILE_ID_HERE/view?usp=drive_link",
    }

```

the link specified for multi_user_csv itself has the "Anyone with the link can view" setting. Then, inside that CSV file, we have something like

```
username,password,csv_link
user1,pass1,https://drive.google.com/file/d/SOME_LONG_FILE_ID1_HERE/view?usp=drive_link
user2,pass2,https://drive.google.com/file/d/SOME_LONG_FILE_ID2_HERE/view?usp=drive_link
user3,pass3,https://drive.google.com/file/d/SOME_LONG_FILE_ID3_HERE/view?usp=drive_link
user4,pass4,https://drive.google.com/file/d/SOME_LONG_FILE_ID4_HERE/view?usp=drive_link
user5,pass5,https://drive.google.com/file/d/SOME_LONG_FILE_ID5_HERE/view?usp=drive_link
```

Each of those CSVs on Google Drive also need to have that same permission setting to ensure the script has access to download them (since it is not leveraging authenticated requests against the Google Drive API).

If you are not using AWS Lambda, and you are simply running it locally on your own server with Docker installed, you can use either Google Drive or local file system paths. You specify which you want to use using the `FILE_SOURCE=[local|google_drive]` environment variable. The local file system paths will leverage mounted volumes on the docker container. Note that outside of AWS Lambda, execution will be driven by **environment variables** rather than **lambda events**. See the [sample.env](sample.env) file for examples for both single_user and multi_user mode.

## Running

### With AWS Lambda

To run the project with AWS Lambda (if you prefer to use files uploaded to Google Drive and drive execution using events with the option of triggering the Lambda function on a schedule or via API calls to an API Gateway):

1. You will need to [install the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) if you have not already done so on your machine.
2. Open AWS Lambda
3. Open the Elastic Container Registry (ECR) service.
4. Create a private repository (any name you'd like to use). No need to change any of the settings. Go ahead and create it.
5. Once you create it, go ahead and open it up. On the top right, you should see a "View Push Commands" button. Click that. This will give you a set of commands you can use to build the Docker image from this project directory and deploy it to that new repository. These commands will depend on the AWS CLI being installed.
6. After you run the provided commands (which will build, tag, and push the docker image to the repository), ECR is all set.
7. Now open the Identity and Access Management (IAM) service. You need to create a role that will allow AWS lambda to use an image from your ECR repository.
8. Open the Roles tab. Click Create Role.
9. Click AWS service for Trusted Entity Type.
10. Click Lambda for the use case. Click Next.
11. On the "Add Permissions" page, in the permissions policies table, search for and check the following two policies:
    a. AWSLambdaBasicExecutionRole - This provides write permissions to CloudWatch Logs.
    b. AmazonEC2ContainerRegistryReadOnly - This provides read-only access to Amazon EC2 Container Registry repositories.
12. Click next. Give the role a meaningful name, like "AWSLambdaBasicWithECRReadAccess". Give it a meaningful description as well, like "Allows Lambda functions to call AWS services on your behalf. Allow use of ECR container images."
13. Create role.
14. Open the Lambda service.
15. Click Create Function.
16. Choose Container Image (select a container image to deploy for your function).
17. Give the function a meaningful name (e.g., bbs-batch-uploader)
18. In a different tab, go back to your ECR repository for a moment, open it, and copy the URI of the image inside of that repository that you just built and pushed using the provided push commands.
19. Now come back to the Lambda function that you are creating, and paste the URI you copied into the Container Image URI field. Leave x86_64 as the architecture.
20. Expand "change default execution role". Choose the role that you just created (it will have the name that you specified). Choose "Use an existing role" and use the existing role dropdown to search for your custom role.
21. Create function.
22. Now that the function is created, open the Configuration tab.
23. Go to Environment variables. Click Edit. Set the following environment variables:

```
PRODUCTION	=    1
WEBDRIVER_TIMEOUT_SECONDS	=   20
WEBDRIVER_UPLOAD_TIMEOUT_SECONDS	=   30
```

24. Go to General configuration, and click Edit.
25. Set Memory to 1024MB. Set Ephemeral storage to 512MB. (downloaded files likely will not be this large; they are always deleted after download). Set Timeout to a value of your choosing; you may want a very long timeout (3 or more minutes) if you are going to be including ten or more users in a multi user mode execution. For just one user at a time, 1 minute is probably a safe bet unless their specific batch upload file is massive.
26. Now you can manually trigger execution of your function using the Test tab. Click Test.
27. Perhaps you want to create a single event for each specific user (named with the corresponding username) formatted in JSON as:

```
{
  "mode": "single_user",
  "verbose": true,
  "single_user_username": "<username>",
  "single_user_password": "<password>",
  "single_user_google_drive_csv_link": "<google drive shared link to batch upload file with Anyone with link can view permission>"
}
```

This would allow / require you to manually execute the function for each individual BBS user.
Alternatively, you could create a single MultiUser event using the multi_user event JSON format shown above in this README.

### Without Lambda

To run the project without AWS Lambda (if you prefer to connect with and use your local file system), take the following steps:

1. Install Docker on the machine which will be running this if you have not already done so.
2. Copy [sample.env](sample.env) to your own `.env` file. Then change the values to match your specifications. The .env file is not included in git version control intentionally to prevent information leakage.
3. In the [docker-compsoe.yml](docker-compose.yml) file, you can feel free to change the value under `volumes`. This is just mapping a host folder (e.g., a `./files` folder in the root of this project) to the main files folder inside the Docker container. So, if you are generating your CSV files for batch uploads and storing them on your server in `/var/bbs-batch-upload-files/` as part of your business process, you could simply change the volumes section to look like:

```
volumes:
  - /var/bbs-batch-upload-files:/opt/data/files
```

You could also change the second part after the colon if you want to change where files are stored inside the container. The key thing to note about that part of the volume is that is the base path you need to use for your environment variables like MULTI_USER_CSV and SINGLE_USER_CSV when using FILE_SOURCE=local.

3. Run `./run-local.sh`. You can [view that script](run-local.sh) to see what it is doing in more detail.
