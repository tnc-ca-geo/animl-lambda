#!/opt/bin/perl

import imageio
import boto3
import requests
import os
import sys
import uuid
import subprocess
from urllib.parse import unquote_plus
import json

ANIML_IMG_API = "https://df2878f8.ngrok.io/api/v1/images/save"
S3_EXTERNAL_DEPS  = "animl-dependencies"
S3_IMAGES_BUCKET  = "animl-images"

s3 = boto3.client('s3')

# fetch exif tool from s3 bucket
s3.download_file(
    S3_EXTERNAL_DEPS,
    'Image-ExifTool-11.89.tar.gz', 
    '/tmp/Image-ExifTool-11.89.tar.gz')
p = subprocess.run('tar -zxf Image-ExifTool-11.89.tar.gz', cwd='/tmp', shell=True)


def make_request(exif_data):
    r = requests.post(ANIML_IMG_API, json=exif_data)
    print(r.status_code)
    # print(r.json())

def get_exif_data(img_path):
    command = '/tmp/Image-ExifTool-11.89/exiftool -json ' + img_path
    p = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True)
    out, err = p.communicate()
    print('successfully extracted exif data: ', out)
    print('error: ', err)
    return json.loads(out)[0]

def handler(event, context):
    for record in event['Records']:
        key = unquote_plus(record['s3']['object']['key'])
        tmpkey = key.replace('/', '')
        tmp_path = '/tmp/{}{}'.format(uuid.uuid4(), tmpkey)
        s3.download_file(S3_IMAGES_BUCKET, key, tmp_path)
        meta_data = get_exif_data(tmp_path)
        meta_data['key'] = key
        meta_data['bucket'] = record['s3']['bucket']['name']
        make_request(meta_data)