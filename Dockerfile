FROM umihico/aws-lambda-selenium-python:latest 
COPY requirements.txt ./
RUN pip3 install -r requirements.txt     
COPY src ${LAMBDA_TASK_ROOT}   
WORKDIR  ${LAMBDA_TASK_ROOT}/src
CMD [ "main.lambda_handler" ] 
