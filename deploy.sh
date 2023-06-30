#!/bin/bash 

# Deploy updated docker image to AWS Elastic Container Registry after code updates 
# Replace these commands with the Push Commands provided by your own Repository. you will first 
# need to run the provided aws ecr get-login-password .... command to log in
docker build -t bizbuysell .
docker tag bizbuysell:latest 636061267657.dkr.ecr.us-east-2.amazonaws.com/bizbuysell:latest
docker push 636061267657.dkr.ecr.us-east-2.amazonaws.com/bizbuysell:latest