#!/bin/bash 

# Deploy updated docker image after code updates 
docker build -t bizbuysell .
docker tag bizbuysell:latest 636061267657.dkr.ecr.us-east-2.amazonaws.com/bizbuysell:latest
docker push 636061267657.dkr.ecr.us-east-2.amazonaws.com/bizbuysell:latest