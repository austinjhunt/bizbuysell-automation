FROM umihico/aws-lambda-selenium-python:latest 
COPY requirements.txt ./
RUN pip3 install -r requirements.txt  
COPY main.py ${LAMBDA_TASK_ROOT} 

# Entrypoint 
CMD [ "main.lambda_handler" ]
