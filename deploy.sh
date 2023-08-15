#!/bin/bash 

# Deploy updated docker image to AWS Elastic Container Registry after code updates 
# Replace these commands with the Push Commands provided by your own Repository. you will first 
# need to run the provided aws ecr get-login-password .... command to log in
docker build -t bbs-uploads-01 .
docker tag bbs-uploads-01:latest 822696483405.dkr.ecr.us-east-1.amazonaws.com/bbs-uploads-01:latest
docker push 822696483405.dkr.ecr.us-east-1.amazonaws.com/bbs-uploads-01:latest
