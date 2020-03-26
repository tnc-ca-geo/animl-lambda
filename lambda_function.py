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
fields_to_keep = {
  "buckeye": [
    "FileName", "MIMEType", "SerialNumber", "DateTimeOriginal", "Model", 
    "ImageWidth", "ImageHeight", "Megapixels"
  ],
}

s3 = boto3.client('s3')

# fetch exif tool from s3 bucket
s3.download_file(
    globalVars['S3-ExternalDeps'],
    'Image-ExifTool-11.89.tar.gz', 
    '/tmp/Image-ExifTool-11.89.tar.gz')
p = subprocess.run('tar -zxf Image-ExifTool-11.89.tar.gz', cwd='/tmp', shell=True)


def filter_std_fields(exif_data, ftk):
    ret = {}
    for field in exif_data:
        if field in ftk:
            ret[field] = exif_data[field]
    return ret

def unpack_comment_field(exif_data):
    ret = {}
    comment = exif_data["Comment"].splitlines()
    for item in comment:
        if "SN=" in item:
            ret["sn"] = item.split("=")[1]
        elif "TEXT1=" in item:
            ret["text_1"] = item.split("=")[1]
        elif "TEXT2=" in item:
            ret["text_2"] = item.split("=")[1]
    return ret

def filter_exif(exif_data_all):
    make = exif_data_all["Make"]
    if make == "BuckEyeCam":
        comment_field_filtered = unpack_comment_field(exif_data_all)
        ret = filter_std_fields(exif_data_all, fields_to_keep["buckeye"])
        ret.update(comment_field_filtered)
        print("exif data filtered: {}".format(ret))
        return ret
    else:
        print("can't process {} images yet".format(make))

def get_meta_data(img_path):
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
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        tmpkey = key.replace('/', '')
        download_path = '/tmp/{}{}'.format(uuid.uuid4(), tmpkey)
        s3.download_file(globalVars['S3-ImagesBucket'], key, download_path)
        fname=key.rsplit('.', 1)[0]
        fextension=key.rsplit('.', 1)[1]
        exif_data_all = get_meta_data(download_path)
        exif_data_filtered = filter_exif(exif_data_all)
        print('filtered exif: {}'.format(exif_data_filtered))