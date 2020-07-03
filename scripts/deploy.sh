#!/bin/bash
#
# Remove old function.zip file
# repackage new one,
# and deploy to aws

rm function.zip
cp output/venv.zip function.zip
zip -u function.zip lambda_function.py
aws-vault exec home -- aws lambda update-function-code --function-name ProcessCamtrapImage \
--zip-file fileb://function.zip