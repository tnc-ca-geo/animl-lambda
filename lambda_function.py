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
FIELDS_TO_KEEP    = {
  "BuckEyeCam": [
    "FileName", "MIMEType", "Make", "Model", "SerialNumber", "DateTimeOriginal", 
    "ImageWidth", "ImageHeight", "Megapixels", "GPSLongitude", "GPSLatitude", 
    "GPSAltitude"
  ],
  "RECONYX": [
    "FileName", "MIMEType", "Make", "Model", "SerialNumber", "DateTimeOriginal", 
    "ImageWidth", "ImageHeight", "Megapixels", "UserLabel"
  ]
}

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

def filter_std_fields(exif_data, ftk):
    ret = {}
    for field in exif_data:
        if field in ftk:
            ret[field] = exif_data[field]
    return ret

def unpack_bec_comment_field(exif_data):
    ret = {}
    comment = exif_data["Comment"].splitlines()
    for item in comment:
        if "SN=" in item:
            ret["SerialNumber"] = item.split("=")[1]
        elif "TEXT1=" in item:
            ret["text_1"] = item.split("=")[1]
        elif "TEXT2=" in item:
            ret["text_2"] = item.split("=")[1]
    return ret

def filter_exif(exif_data_all):
    make = exif_data_all["Make"]
    ret = filter_std_fields(exif_data_all, FIELDS_TO_KEEP[make])
    if make == "BuckEyeCam":
        comment_field_filtered = unpack_bec_comment_field(exif_data_all)
        ret.update(comment_field_filtered)
    return ret

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
        # bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])
        tmpkey = key.replace('/', '')
        download_path = '/tmp/{}{}'.format(uuid.uuid4(), tmpkey)
        s3.download_file(S3_IMAGES_BUCKET, key, download_path)
        # fname=key.rsplit('.', 1)[0]
        # fextension=key.rsplit('.', 1)[1]
        exif_data_all = get_meta_data(download_path)
        exif_data_filtered = filter_exif(exif_data_all)
        exif_data_filtered['Path'] = key
        print('filtered exif: {}'.format(exif_data_filtered))
        make_request(exif_data_filtered)
        