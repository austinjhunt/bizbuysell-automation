#!/bin/bash

# The Docker image uses an AWS Lambda base image which comes with a Lambda runtime interface emulator
# built in. Basically, the image is built to assume all interactions with the function 
# are coming through AWS Lambda. But we can simulate that Lambda interaction locally by 
# 1) Running the container locally 
# and 2) Posting a fake JSON "event" to the local container (similar to how you'd post a 
# real JSON event to an AWS Lambda function)

# This script wraps that process up so you can simply execute ./run-local.sh to run the local 
# container after you've set up your .env variables as desired. 

echo "Building image with latest source code changes" 
docker-compose build 

echo "Running docker container in background using new image"
docker-compose up -d 

echo "Using CURL to post a fake "event" to simulate AWS Lambda interaction and trigger execution"
echo "Run docker logs bizbuysellautomator --follow in a different terminal window to follow what happens after this event"
curl -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{}'