# BizBuySell Automator

This is a project completed for an UpWork freelance job (for client Robin Gagnon and [Connor Thompson](mailto:connor@wesellrestaurants.com)). The project leverages Selenium and Python to automate the batch uploading of business listings in CSV format to [BizBuySell](https://bizbuysell.com), the Internet's largest business for sale exchange.

## Phase 1 Problem Statement (6/25/2023)

- We need a script that will mimic the steps we take to log into a website with the user credentials and do a batch upload of a .csv file and then log out.
- We will need to duplicate this process 30 times for 30 different user accounts so in addition to the script I need the ability to know where to edit the script to substitute:
  - Different user name and login credentials
  - Different location for the source file

## Phase 2 Problem Statement (7/13/2023)

- We need to be able to use [AWS S3](https://aws.amazon.com/s3/) as the file source
- We want to avoid getting blocked while automating web requests against [bizbuysell.com](https://bizbuysell.com) so we need to rotate IP addresses at intervals

## Why I Used [Docker](https://www.docker.com/) and [ECR](https://aws.amazon.com/ecr/)

I completed the first phase of project after approximately 21 hours of work. The main obstacle was not development with Selenium, but was finding the proper web driver and browser binaries that would be compatible with the AWS Lambda environment. I started out as most do, intending to just build out the project locally, test it, then zip the whole thing up (with the Python packages, the web driver, and the Chrome binary) and upload the zip file to AWS Lambda to create a new function. Nope. Size limitations of Lambda ultimately led me to use [a Docker image from umihico on GitHub](https://github.com/umihico/docker-selenium-lambda/tree/main) since the use of container images comes with a **much more lenient size requirement**. This approach allows execution of the function without having to use S3 for separate storage of large binaries or separate layers in Lambda to split up the project into size-limited chunks (as some tutorials suggested). Instead, I could now just build the whole project with its dependencies into a single Docker image (`docker build -t bizbuysellautomator .`) and deploy it to [Elastic Container Registry](https://aws.amazon.com/ecr/). Moreover, one can also run it outside of AWS entirely on any machine with Docker installed. The [umihico Docker image](https://github.com/umihico/docker-selenium-lambda/tree/main) has the latest Chrome web driver and browser built in so no need to go searching for and downloading those (large) files unless you want to do further development and testing outside of the Docker image from umihico.

## IP Address Rotation

### Idea 1: Tor and Stem

To address the problem of rotating IP addresses, I first looked into a very commonly suggested approach of using [stem](https://pypi.org/project/stem/) and [Tor](https://www.torproject.org/) to funnel outbound traffic through proxy nodes that serve to disguise the true source IP. I updated the Docker image to include a from-source installation of Tor with a custom config file, as well as the `stem` Python package. Stem definitely addressed the goal of changing the public IP, pretty easily too. Unfortunately, it seems the destination website [bizbuysell](https://bizbuysell.com) is configured to blacklist the exit nodes of the Tor network, so all requests through that Tor network were coming back with an "Access denied from this server" error.

### Idea 2: Dynamic association of Elastic IPs with boto3

With Tor being a failed pursuit, I thought of another possible approach; could a running Lambda function perhaps change its own IP while executing by modifying a VPC to which it is attached? I first built a VPC allowing outbound internet access using [this great tutorial from GokceDB on YouTube](https://www.youtube.com/watch?v=Z3dMhPxbuG0&ab_channel=GokceDB), and added the Lambda function to that VPC. I then added a network utility module that leveraged Boto3 to do (well, try to do) the following:

1. Get the current Elastic IP address in use the Lambda function's network interface (ENI)
2. Disassociate that Elastic IP address from its ENI
3. release that Elastic IP fully
4. Allocate a new Elastic IP
5. Associate that new Elastic IP to the same ENI

Unfortunately, the disassociation operation was not allowed despite the necessary EC2 policies being granted to the role executing the operation.

### :star2: :star2: Idea 3: UpdateFunctionCode :star2: :star2:

I came across [this video from Armando Sepulveda on YouTube](https://www.youtube.com/watch?v=8BbOVhHs950&ab_channel=ArmandoSepulveda-RealEstateAutomations) which explains a surprisingly simple method of rotating IP addresses of a running Lambda function. The key: re-deploying the function. The cool thing is that the Lambda client from `boto3` offers a method called `update_function_code` that allows one to automate the redeployment of a function. The even cooler thing is that the function itself can leverage this. So, I have just added an invocation to `update_function_code` after the execution of the main process. This is non-blocking, which means the function will start that new deployment but will continue with returning the HTTP response from the most recent execution. Each new invocation of the function runs it from a new IP triggered by the last invocation's redeployment of itself. To make this clear, I added an "ip" key in the JSON response from the Lambda function.

## Project Details

This project addresses the base problem statement in a way that is fully parameterized in order to avoid the need for manual work after an initial setup phase. Moreover, after correspondence with Connor over email about the details of the upload process, the function is now able to fully handle both the **update of existing business listing records** as well as the **import of new business listing records** with default values selected for listing type and business type on new imports, which will help to reduce the amount of manual work that needs to be done after the automation completes.

### Parameters (see [sample.env](sample.env))

The key parameters that drive execution of the automation can be defined either as environment variables or as event payload arguments when invoking AWS Lambda. If a given variable is defined in both the event and in the environment variables, priority is given to the event. This means that you can override the environment when necessary just using the request payload without having to log in and actually change environment variables.

#### PRODUCTION (default=0)

Production status determines what paths are used for the chrome drivers (in production, they live in a static folder in the docker image but development, you may download them from https://googlechromelabs.github.io/chrome-for-testing/#stable (chrome binary) and https://chromedriver.storage.googleapis.com/index.html?path=114.0.5735.90/ (chrome driver). `PRODUCTION` also determines temporary file directories and whether to use the `--headless` arg for the browser. If 0, headless is not used and you can watch the automated browser actions in a GUI (only if you are developing outside of Docker, just using `python <script>` in a terminal.)

#### VERBOSE (default=0)

Use VERBOSE=1 to enable verbose logging (debug) or VERBOSE=0 to use normal logging (info)

#### WEBDRIVER_TIMEOUT_SECONDS (default=15)

Base webdriver timeout for actions like waiting for elements to appear, and basic front-end operations. Intentionally separate from the timeout for upload operations (`WEBDRIVER_UPLOAD_TIMEOUT_SECONDS`) which should take longer. You should tune this as necessary if you notice any timeout exceptions occurring, assuming you are running from a device with internet access.

#### WEBDRIVER_UPLOAD_TIMEOUT_SECONDS (default=30)

Timeout used by webdriver for upload operations. You should tune this as necessary if you notice any timeout exceptions occurring, assuming you are running from a device with internet access.

#### FILE_SOURCE (default=None - you must explicitly define)

This variable defines the file source you'd like to use (where are the batch CSV files that need to be uploaded?). Opttions:

- `FILE_SOURCE=s3` - use AWS S3 as the file source (requires `AWS_S3_REGION` and `AWS_S3_BUCKET` to be set):

  - `AWS_S3_BUCKET` (default=None - you must explicitly define) - Specify the name of your S3 bucket containing your files. Recommended use: a single "Multi User" CSV file as described below lives in the bucket and it references N other user files that are also stored in the same bucket with the corresponding credentials for each of those. See

  - `AWS_S3_REGION` (default=None - you must explicitly define) - Specify the AWS region in which your bucket lives, e.g., `us-east-2`

- `FILE_SOURCE=local` - use local file system as file source
- `FILE_SOURCE=google_drive` - use Google Drive as file source; if using Google Drive, you must use "Anyone with the link can view" permission setting on all shared CSV links

#### AWS_ACCESS_KEY_ID (default=None) and AWS_SECRET_ACCESS_KEY (default = None)

These parameters should not be stored as environment variables or passed as event payload arguments if you are running with AWS Lambda. If you are running with AWS Lambda, the better option is to use the [IAM](https://aws.amazon.com/iam/) service to create a role with an attached policy that **grants access to your S3 bucket (specifically)** and assign that as the execution role for your Lambda function. If you are running **outside of AWS Lambda** and are using AWS S3 as a file source (`FILE_SOURCE=s3`), the [local handler](src/main.py) will first verify that both of these credentials are provided before continuing and will return an error if they are not present.

#### MODE (default=single_user)

This one is especially important; this tells the driver which mode to use. Below is a description of the two modes:

- **single_user** - use this mode if you only need to execute automation for a single user's account. This mode requires the following additional parameters:

  - `SINGLE_USER_USERNAME` (default=None - must explicitly provide) - username of the specific user whose session is being automated
  - `SINGLE_USER_PASSWORD` (default=None - must explicitly provide) - password of the specific user whose session is being automated
  - `SINGLE_USER_CSV` (default=None - must explicitly provide) - value depends on `FILE_SOURCE`:
    - if `FILE_SOURCE=local`, this is the local path to the single user's batch upload file; the path should start with the container path used in the files volume from [docker-compose.yml](docker-compose.yml); for example, if volume in docker-compose.yml is `- /Users/coolguy/data/files:/opt/data/files`, you could store your file in this project folder at `/Users/coolguy/data/files/myfile.csv` and then set `SINGLE_USER_CSV=/opt/data/files/myfile.csv`
    - if `FILE_SOURCE=s3`, this is the path to the single user's batch upload file starting from the root of your `AWS_S3_BUCKET` (e.g., if it's in the base of the bucket with no subfolders, it is just the file name)
    - if `FILE_SOURCE=google_drive`, this is the copied link to the single user's batch upload file stored in Google Drive with "Anyone with the link can view" permission settings

- **multi_user** - use this mode if you want to automate sessions for multiple users with a single invocation of the function. This requires an additional parameter:
  - `MULTI_USER_CSV` (default=None - must explicitly provide). This is a CSV the MUST have the following column headers: `username,password,csv_path`; it outlines the credentials and the location of the batch upload CSV for **each user** whose session is to be automated. The specific format of the value depends on `FILE_SOURCE`:
    - if `FILE_SOURCE=local` then this is the local path to the multi user CSV file; the path should start with the container path used in the files volume from [docker-compose.yml](docker-compose.yml); for example, if volume in docker-compose.yml is `- /Users/coolguy/data/files:/opt/data/files`, you could store your file in this project folder at `/Users/coolguy/data/files/multiuser.csv` and then set `SINGLE_USER_CSV=/opt/data/files/multiuser.csv`, and each value of `csv_path` in `multiuser.csv` must follow the same format! Example: the user records in that CSV file path may each look like `usera@gmail.com,supersecretpassword,/opt/data/files/users/usera.csv`
    - if `FILE_SOURCE=s3` then this is the path to the multi user CSV file starting from the root of your `AWS_S3_BUCKET`; each value of `csv_path` in the multi user CSV must follow the same format! Example: the user records in that CSV file path may each look like `usera@gmail.com,supersecretpassword,files/usera.csv`
    - if `FILE_SOURCE=google_drive` then this is the copied link to the multi user CSV file stored in Google Drive with "Anyone with the link can view" permission settings; each value of `csv_path` in the multi user CSV must follow the same format! Example: the user records in that CSV file path may each look like `usera@gmail.com,supersecretpassword,<copied link with Anyone can view permissions to usera@gmail.com's batch upload file in Google Drive>`

#### AWS_LAMBDA_ARN (default=None) - required for AWS Lambda execution

You must provide the ARN of the lambda function in order for the IP address rotation to work; that rotation depends on the update_function_code(...) function from boto3 which requires the ARN as an argument. Basically, the new code deployment (even if there are no changes) triggers the association of a new IP address (to avoid blocks due to automation)

#### AWS_LAMBDA_ECR_IMAGE_URI (default=None) - required for AWS Lambda Execution

Once you create an ECR repository and you have pushed the docker image for this project into that repository (using the commands from the `View push commands` link within your repository), copy the `:latest` URI and paste that as the value for AWS_LAMBDA_ECR_IMAGE_URI; it is important that you use the `:latest` image.

If you are not using AWS Lambda, and you are simply running it locally on your own server with Docker, you can use any `FILE_SOURCE` (`local`, `google_drive`, or `s3`). The local file system paths will leverage mounted volumes on the docker container. See [sample.env](sample.env) for a detailed example. Remember that if you are running it locally with `FILE_SOURCE=s3`, you must provide your AWS credentials (`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`).

All of the parameters outlined above can be passed either in the event payload to the handler functions or can be set as environment variables.

#### CREDENTIALS_FILE

USE THIS VARIABLE WHEN TRIGGERING WITH S3 NOTIFICATIONS. S3 notifications don't include credentials, so this environment variable points to a CSV file in the `AWS_S3_BUCKET` that is formatted _exactly_ as follows (use the same column headings):

```
Office,Agent,Email,Password,File Name,,,
Austin, FirstName LastName, someusername@somedomain.com, userPassword, filename.csv,,,
```

This format is based on an initial file that was provided during initial setup of S3 event notifications. Any change to this format (particularly changes to the Email or Password column headings) will break the extraction of credentials needed for the Lambda to work.

## Running

### With AWS Lambda

To run the project with AWS Lambda (very useful if you want to drive execution using events with the option of triggering the Lambda function on a schedule or via API calls to an API Gateway):

1. You will need to [install the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) if you have not already done so on your machine.
2. Open AWS.
3. Open the Elastic Container Registry (ECR) service.
4. Create a private repository (any name you'd like to use). No need to change any of the other settings. Go ahead and create it.
5. Once you create it, open it up. On the top right, you should see a "View Push Commands" button. Click that. This will give you a set of commands you can use to build the Docker image from this project directory and deploy it to that new repository. These commands will depend on the AWS CLI being installed (see step 1). You should go ahead and replace the lines in [deploy.sh](deploy.sh) with your own push commands that you just obtained.
6. After you run the provided commands (which will build, tag, and push the docker image to the repository), ECR is all set.
7. Now open the Identity and Access Management (IAM) service. You need to create a role that will allow AWS lambda to do some key things: use the image from your ECR repository, update function code, access your S3 files, and of course execute.
8. Open the Roles tab. Click Create Role.
9. Click AWS service for Trusted Entity Type.
10. Click Lambda for the use case. Click Next.
11. We need to create a custom policy to grant permission to the Lambda to update its own function code and access your S3 bucket. Click Create Policy. This will open a new tab. We will return back to the Role tab in a moment. Under Select a Service, choose the lambda service. Choose the "Write" dropdown. Check "UpdateFunctionCode". Under Resources, choose Specific, and click Add ARN to restrict access. Choose "This account", provide the region in which your function will live (e.g., us-east-2), and provide the name of your Lambda function (you haven't created it yet, but enter the name you plan on using.) Click Add ARNS.
12. IF YOU ARE GOING TO USE S3 AS A FILE SOURCE: Click Add more permissions. Select S3 as the service. Check "All S3 actions (S3:\*)". Under Resources, choose specific, and next to "bucket", click Add ARN. Provide the name of the S3 bucket you are going to use (if you haven't already created a bucket, enter the name you plan on using). Click Add ARNS. Now, next to object, choose Add ARN to restrict access. Provide the bucket name again, and then check "any object name". Click Add ARNs.At this point, if you click the JSON editor, you'll have something like this:

```
{
	"Version": "2012-10-17",
	"Statement": [
		{
			"Sid": "VisualEditor0",
			"Effect": "Allow",
			"Action": [
				"lambda:UpdateFunctionCode",
				"s3:*"
			],
			"Resource": [
				"arn:aws:lambda:REGION:OWNER_ACCOUNT_NUMBER:function:FUNCTION_NAME",
				"arn:aws:s3:::BUCKETNAME",
				"arn:aws:s3:::BUCKETNAME/*"
			]
		},
		{
			"Sid": "VisualEditor1",
			"Effect": "Allow",
			"Action": [
				"s3:ListStorageLensConfigurations",
				"s3:ListAccessPointsForObjectLambda",
				"s3:GetAccessPoint",
				"s3:PutAccountPublicAccessBlock",
				"s3:GetAccountPublicAccessBlock",
				"s3:ListAllMyBuckets",
				"s3:ListAccessPoints",
				"s3:PutAccessPointPublicAccessBlock",
				"s3:ListJobs",
				"s3:PutStorageLensConfiguration",
				"s3:ListMultiRegionAccessPoints",
				"s3:CreateJob"
			],
			"Resource": "*"
		}
	]
}
```

14. Click Next. Give the Policy a meaningful name (e.g., LambdaUpdateFunctionCodeAndAccessS3Bucket) and a meaningful description outlining the permissions you selected. ("Allows the UpdateFunctionCode operation on Lambda with name `<myLambdaFunctionName>` and allows full S3 access to my S3 bucket `<myBucketName>`"). Click create policy. Now, go back to the previous tab where you are adding permissions to the new Role. Since you just added a new policy, you may need to click the refresh button on the table (not the browser).
15. Search for and check the following three policies:
    a. The one you just created (e.g., "LambdaUpdateFunctionCodeAndAccessS3Bucket")
    a. AWSLambdaBasicExecutionRole - This provides write permissions to CloudWatch Logs.
    b. AmazonEC2ContainerRegistryReadOnly - This provides read-only access to Amazon EC2 Container Registry repositories.
16. Click next. You should see 3 total policies under your permissions policy summary. Give the role a meaningful name, like `"<MyLambdaFunctionName>ExecutionRole"`. Give it a meaningful description as well, like "Allows Lambda functions to call AWS services on your behalf. Allow use of ECR container images. Allows access to my S3 bucket `<name>`. Allows UpdateFunctionCode on my Lambda function `<name>`"
17. Create role.
18. Open the Lambda service.
19. Click Create Function.
20. Choose Container Image (select a container image to deploy for your function).
21. Give the function a meaningful name (e.g., bbs-batch-uploader)
22. In a different tab, go back to your ECR repository for a moment, open it, and copy the URI of the image inside of that repository that you just built and pushed using the provided push commands. Be sure to replace `@sha...` with just `:latest` to ensure the function will stay updated with the latest deployed image in the repository.
23. Now come back to the Lambda function that you are creating, and paste the Image URI you copied into the `Container Image URI` field. Leave `x86_64` as the architecture.
24. Expand "change default execution role". Choose "Use an existing role" and use the existing role dropdown to search for your custom role (it will have the name that you specified).
25. Create function.
26. Now that the function is created, open the Configuration tab.
27. Go to Environment variables. Click Edit. Set the following environment variables (you may want to modify these if you notice later that your function is timing out):

```
PRODUCTION (use 1)
VERBOSE	(1 or 0)
AWS_LAMBDA_ARN
AWS_LAMBDA_ECR_IMAGE_URI
AWS_S3_BUCKET
AWS_S3_REGION
FILE_SOURCE
MODE
MULTI_USER_CSV (if MODE=multi_user)
SINGLE_USER_CSV (if MODE=single_user)
SINGLE_USER_PASSWORD  (if MODE=single_user)
SINGLE_USER_USERNAME (if MODE=single_user)
WEBDRIVER_TIMEOUT_SECONDS (tune this as necessary, may take trial and error)
WEBDRIVER_UPLOAD_TIMEOUT_SECONDS (tune this as necessary, may take trial and error)
```

24. Go to General configuration, and click Edit.
25. Set Memory to 1024MB. Set Ephemeral storage to 512MB. (downloaded files likely will not be this large; they are always deleted after download). Set Timeout to a value of your choosing; you may want a very long timeout (3 or more minutes) if you are going to be including ten or more users in a multi user mode execution. For just one user at a time, 1 minute is probably a safe bet unless their specific batch upload file is massive. For reference, 1m30s timed out for multi_user mode with the **five** test users that were provided.
26. Now you can manually trigger execution of your function using the Test tab. Click Test. If you have all of those values stored as environment variables, your Test event doesn't necessarily need any payload values, but you can pass them here as well if you want to override your environment variables.
27. Perhaps you want to create a single event for each specific user (named with the corresponding username) formatted in JSON as:

```

{
"MODE": "single_user",
"VERBOSE": true,
"SINGLE_USER_USERNAME": "<username>",
"SINGLE_USER_PASSWORD": "<password>",
"SINGLE_USER_CSV": "path to csv file from base of S3 bucket, e.g. userfiles/userA.csv, or just userA.csv if it's in the root of the bucket"
}

```

This would allow you to manually execute the function for each individual BBS user.

Alternatively, you could create a single MultiUser event using the multi_user mode described in this README, and work off the assumption that the multi user CSV specified will always include the updated `username,password,csv_path` values for all of the users in question.

```

{
"MODE": "multi_user",
"VERBOSE": true,
"MULTI_USER_CSV": "path to a username,password,csv_path CSV file from base of S3 bucket, e.g. files/allusers.csv, or just allusers.csv if it's in the root of the bucket; the column csv_path in this CSV should have values formatted the same way!"
}

```

### Without Lambda

To run the project without AWS Lambda, take the following steps:

1. Install Docker on the machine which will be running this if you have not already done so.
2. Copy [sample.env](sample.env) to your own `.env` file. Then change the values to match your specifications. The .env file is not included in git version control intentionally to prevent information leakage.
3. In the [docker-compose.yml](docker-compose.yml) file, you can feel free to change the value under `volumes`. This is just mapping a host folder (e.g., a `./files` folder in the root of this project) to the main files folder inside the Docker container. So, if you are generating your CSV files for batch uploads and storing them on your server in `/var/bbs-batch-upload-files/` as part of your business process, you could simply change the volumes section to look like:

```

volumes:

- /var/bbs-batch-upload-files:/opt/data/files

```

You could also change the second part after the colon if you want to change where files are stored inside the container. The key thing to note about the part after the colon is that is the base path you need to use for your environment variables like MULTI_USER_CSV and SINGLE_USER_CSV when using FILE_SOURCE=local (i.e., frame your local paths from the perspective of the container). You can also add multiple volumes if you have different locations on your host server storing different groups of files.

3. Run `./run-local.sh`. You can [view that script](run-local.sh) to see what it is doing in more detail.
4. As the output of that script indicates, open a separate terminal window and run: `docker logs bizbuysellautomator --follow` to follow the logs of your running container.

### Phase 3: Triggering with S3 Notification Event

Following a meeting with Greg Cory on 8/10/2023, some updates have been made to the project.

The client is bulk uploading files into an S3 bucket, and they're not in a position currently where they can script the upload of those files and immediately invoke an API Gateway call to trigger the Lambda (which would allow them to update an S3 file, then make an HTTP API request with a payload containing the file info and its corresponding credentials). For the time being, they need a way of triggering the lambda whenever a file is updated in S3. This is easy enough to do by setting up notification events on the S3 bucket. The tricky part is, when a file is updated in the bucket, how can you send the creds corresponding to that updated file to the Lambda function? First thought: use metadata on the file. I tried this, but it doesn't work because any time you upload a file, the metadata is empty, and if the file is being updated (i.e. an upload with the same name), any existing metadata is wiped clean. Plus, it's a little slower, because the metadata is not passed in the event, so you still have to read it from the file by using boto3 and the file key. And you have to either script the upload process to maintain /clone existing metadata, or you have to manually go back in and re-enter username and password for each file you upload in the browser. Big headache.

So instead, when using S3 updates as the trigger, we pull the creds from an S3 CSV file defined with a new environment variable called `CREDENTIALS_FILE`, e.g., `CREDENTIALS_FILE=bbs-user-logins.csv`. Now, when the function gets a notification that a file with key `bbs/someFileKey.csv` was updated, it pulls the creds for that file from the `CREDENTIALS_FILE` by reading it from S3, and runs with `MODE=single user`. (the assumption with S3 trigger is always single user mode since each individual file update triggers its own lambda execution).

I've added a section to the `lambda_handler` in [main.py](src/main.py) to check if the function is being triggered by an S3 notification event. If it is, it runs a newly added `driver.handle_s3_trigger_single_user_mode(s3_bucket,s3_updated_file_key)` method (in [driver.py](src/driver.py)), where both `s3_bucket` and `s3_updated_file_key` are pulled from the S3 event notification.

### 8/17/2023 - How It's Working:

1. Client has an ECR repository `bbs-uploads-01` in region `us-east-1`. The Docker image built with the [Dockerfile](Dockerfile) is deployed to that repository using the [deploy.sh](deploy.sh) script.
2. Client has a Lambda function also in the region `us-east-1`. That Lambda uses the the `:latest` image URI from the aforementioned ECR repository `bbs-uploads-01`. Lambda function execution role is `BBS-Uploads-ExecutionRole` allowing self-deployment, ECR image reads, and S3 file reads. Lambda timeout is 1 minute since the expectation here is for it to run for a single user at a time (MODE=single_user).
3. Client will use a bucket `wsr-integrations`. All file uploads (individual files, not zipped) will go into a `bbs` folder inside of the `wsr-integrations` bucket.
4. An event notification `bbs-upload-event` is configured to notify the `bizbuysell` Lambda function of **all object create events** (new uploads and overwrites of existing files) for files with prefix `bbs` (i.e., inside `bbs` folder).
5. These event notifications happen for **each individual file**, even if uploading many at once. Each event notification carries the key of the updated file (e.g., `bbs/WSR Clermont.csv`). The Lambda function, when triggered by this notification, uses that file key to first obtain creds for it, download it from S3, and upload it to BBS.
6. **Reading creds:** The Lambda reads the `CREDENTIALS_FILE` specified as an environment variable from the root of the same S3 bucket `wsr-integrations` and pulls the creds corresponding to the file with the file key from the trigger event. NOTE: **This CREDENTIALS_FILE is stored in the root of the same bucket** `wsr-integrations`, not in the `bbs` folder. This is because updates to this credentials file should not trigger the Lambda function. If the credentials file does not contain creds for a given file that triggers the Lambda, an error will be returned.
7. The Lambda downloads the file using the key from the S3 trigger event.
8. The Lambda uses the credentials from `CREDENTIALS_FILE` to automate the upload of the downloaded file to bizbuysell.com.
