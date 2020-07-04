#!/bin/bash
#
# Deploy lambda function to aws

# Remove old function.zip file
rm function.zip

# repackage new one
cp output/venv.zip function.zip
zip -u function.zip lambda_function.py

# and deploy to aws
#   NOTE: the function and all zipped dependencies get placed in /var/task
#   in the lambda runtime environment.
#   also accessible via the env variable $LAMBDA_TASK_ROOT
aws-vault exec home -- aws lambda update-function-code --function-name ProcessCamtrapImage \
--zip-file fileb://function.zip