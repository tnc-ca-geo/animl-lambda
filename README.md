# animl-lambda
Lambda function for processing camera trap images.

## Related repos
- Animl base program      http://github.com/tnc-ca-geo/animl-base
- Animl ML resources      http://github.com/tnc-ca-geo/animl-ml
- Animl desktop app       https://github.com/tnc-ca-geo/animl-desktop
- Animl cloud platform    https://github.com/tnc-ca-geo/animl

## About
The entire stack is a collection of AWS resources managed by the Serverless framework. Any images uploaded to the ```animl-staging-<stage>``` bucket are processed by a lambda function that:
  - extracts EXIF metadata
  - creats a thumbnail of the image
  - stores both the thumbnail and the original in separate buckets for archive & production access
  - passes along the metadata in a request to a server to create a record of the image metadata in a database

## Setup

### Prerequisits
The instructions below assume you have the following tools globally installed:
- serverless
- docker

### Create "serverless-admin" AWS config profile

### Make a project direcory and clone this repo
```
mkdir animl-lambda
cd animl-lambda
git clone https://github.com/tnc-ca-geo/animl-lambda.git
```

### Clone serverless-pyton-requirements plugin
This project runs in a lambda python environment, which means that all python dependencies must be installed in the OS in which the will be ultimately executed. To accomplish this we use a Serverless plugin called [serverless-python-requirements](https://www.serverless.com/plugins/serverless-python-requirements) that, on ```serverless deploy```, spins up a Docker container to mimic the AWS lambda linux OS, downloads any Python requirements defined in ```requirements.txt``` within the container, and packages them up to be added to our lambda deployment package. 

The plugin works well for for installing python packages, but we also need to include a Perl executable (exiftool) and its dependencies in the final deployment package, and the serverless-python-requirements plugin doesn't support some functionalty that we need to make that happen out of the box (see issue [here](https://github.com/UnitedIncome/serverless-python-requirements/issues/542)). I created a fix and [pull request](https://github.com/UnitedIncome/serverless-python-requirements/pull/544) to support this, but until the PR is accepted we have to clone the repo into our project manually from my github profile:

```
mkdir .serverless_plugins
cd .serverless_plugins
git clone --single-branch --branch recursive-docker-extra-files https://github.com/nathanielrindlaub/serverless-python-requirements.git
cd serverless-python-requirements
npm install
```

## Deployment
From project root folder (where ```serverless.yml``` lives), run the following to deploy or update the stack: 

```
# Deploy a dev stack:
serverless deploy --stage dev

# Deploy a prod stack:
serverless deploy --stage prod
```

## Adding new Python packages

### Create venv and activate it
```
virtualenv venv --python=python3
source venv/bin/activate
```

### Add dependencies
```
# Example package installs
pip install pillow
pip install requests
pip install PyExifTool
```

### Freeze dependenceies in requirements.txt
```
pip freeze > requirements.txt

# Deactivate venv when you're done
deactivate
```