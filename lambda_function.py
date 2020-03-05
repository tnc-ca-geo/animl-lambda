#!/opt/bin/perl

import imageio
import boto3
import os
import sys
import uuid
import subprocess
from urllib.parse import unquote_plus
import json


globalVars  = {}
globalVars['S3-ExternalDeps']   = 'animl-dependencies'
globalVars['S3-ImagesBucket']   = 'animl-images'

s3 = boto3.client('s3')

# fetch exif tool from s3 bucket
s3.download_file(
    globalVars['S3-ExternalDeps'],
    'Image-ExifTool-11.89.tar.gz', 
    '/tmp/Image-ExifTool-11.89.tar.gz')
p = subprocess.run('tar -zxf Image-ExifTool-11.89.tar.gz', cwd='/tmp', shell=True)

def get_meta_data(img_path):
    command = '/tmp/Image-ExifTool-11.89/exiftool -json ' + img_path
    p = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True)
    out, err = p.communicate()
    print('success. exif data: ', out)
    print('error: ', err)

def handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        tmpkey = key.replace('/', '')
        download_path = '/tmp/{}{}'.format(uuid.uuid4(), tmpkey)
        s3.download_file(globalVars['S3-ImagesBucket'], key, download_path)
        fname=key.rsplit('.', 1)[0]
        fextension=key.rsplit('.', 1)[1]
        get_meta_data(download_path)