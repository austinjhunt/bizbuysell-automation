FROM umihico/aws-lambda-selenium-python:latest   
COPY requirements.txt ./
RUN pip3 install -r requirements.txt  
COPY lambda_function.py ${LAMBDA_TASK_ROOT} 

# Entrypoint 
CMD [ "lambda_function.lambda_handler" ]
