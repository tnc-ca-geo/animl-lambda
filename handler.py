#!/opt/bin/perl

import os
import uuid
import ntpath
from urllib.parse import unquote_plus
import hashlib
from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True
import boto3
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
import exiftool
from lambda_cache import ssm


PROD_DIR_IMGS = "images"
PROD_DIR_THUMB = "thumbnails"
EXIFTOOL_PATH = "{}/exiftool".format(os.environ["LAMBDA_TASK_ROOT"])
SUPPORTED_FILE_TYPES = [".jpg", ".png"]
THUMB_SIZE = (120, 120)
SSM_NAMES = {
    "ANIML_API_URL": "animl-api-url-{}".format(os.environ["STAGE"]),
    "ARCHIVE_BUCKET": "animl-images-archive-bucket-{}".format(os.environ["STAGE"]),
    "PROD_BUCKET": "animl-images-prod-bucket-{}".format(os.environ["STAGE"]),
    "DEADLETTER_BUCKET": "animl-images-dead-letter-bucket-{}".format(os.environ["STAGE"]),
}
QUERY = gql("""
    mutation CreateImageRecord($input: CreateImageInput!){
        createImage(input: $input) {
            image {
                _id
                objectKey
            }
        }
    }
"""
)

s3 = boto3.client("s3")

def create_thumbnail(md, config, size=THUMB_SIZE, dir=PROD_DIR_THUMB):
    print("Creating thumbnail")
    prod_bkt = config["PROD_BUCKET"]
    file_ext = os.path.splitext(md["FileName"])
    thumb_filename = "{}-small{}".format(md["Hash"], file_ext[1])
    tmp_path_thumb = os.path.join("/tmp", thumb_filename)
    with Image.open(md["SourceFile"]) as image:
        image.thumbnail(size)
        image.save(tmp_path_thumb)
    print("Transferring thumbnail {} to {}".format(thumb_filename, prod_bkt))
    thumb_key = os.path.join(dir, thumb_filename)
    s3.upload_file(tmp_path_thumb, prod_bkt, thumb_key)

def copy_to_dlb(errors, md, config):
    dl_bkt = config["DEADLETTER_BUCKET"]
    copy_source = { "Bucket": md["Bucket"], "Key": md["Key"] }
    dest_dir = "UNKNOWN_ERROR"
    for error in errors:
        if "extensions" in error and "code" in error["extensions"]:
            dest_dir = error["extensions"]["code"]
    md["DeadLetterKey"] = os.path.join(dest_dir, md["FileName"])
    # transfer to dead letter bucket
    print("Transferring {} to {}".format(md["FileName"], dl_bkt))
    s3.copy(copy_source, dl_bkt, md["DeadLetterKey"])

def copy_to_dest(md, config):
    archive_bkt = config["ARCHIVE_BUCKET"]
    prod_bkt = config["PROD_BUCKET"]
    copy_source = { "Bucket": md["Bucket"], "Key": md["Key"] }
    # transfer to archive
    print("Transferring {} to {}".format(md["FileName"], archive_bkt))
    s3.copy(copy_source, archive_bkt, md["ArchiveKey"])
    # transfer to prod
    print("Transferring {} to {}".format(md["FileName"], prod_bkt))
    s3.copy(copy_source, prod_bkt, md["ProdKey"])
    return md

def save_image(md, config, query=QUERY):
    print("Posting metadata to API: {}".format(md))
    url = config["ANIML_API_URL"]
    image_input = {"input": { "md": md }}
    transport = RequestsHTTPTransport(
        url, verify=True, retries=3,
    )
    client = Client(transport=transport, fetch_schema_from_transport=True)
    try:
        r = client.execute(query, variable_values=image_input)
        print("Response: {}".format(r))
        copy_to_dest(md, config)
        create_thumbnail(md, config)
    except Exception as e:
        print("Error posting to backend: {}".format(e))
        errors = vars(e).get("errors", [])
        copy_to_dlb(errors, md, config)

def hash(img_path):
    image = Image.open(img_path)
    img_hash = hashlib.md5(image.tobytes()).hexdigest()
    return img_hash

def enrich_meta_data(md, exif_data, config):
    exif_data.update(md)
    md = exif_data
    md["Hash"] = hash(md["SourceFile"])
    file_base, file_ext = os.path.splitext(md["FileName"])
    archive_filename = file_base + "_" + md["Hash"] + file_ext
    md["SerialNumber"] = md.get("SerialNumber") or "unknown"
    md["ArchiveKey"] = os.path.join(md["SerialNumber"], archive_filename)
    md["ProdKey"] = os.path.join(PROD_DIR_IMGS, md["Hash"] + file_ext)
    md["ProdBucket"] = config["PROD_BUCKET"]
    return md

def get_exif_data(img_path):
    os.environ["PATH"] = "{}:{}/".format(os.environ["PATH"], EXIFTOOL_PATH)
    with exiftool.ExifTool() as et:
        ret = {}
        exif_data = et.get_metadata(img_path)
        # remove "group names" from keys/exif-tags
        for key, value in exif_data.items():
            # print("exif key: {}, value: {}".format(key, value))
            new_key = key if (":" not in key) else key.split(":")[1]
            ret[new_key] = value
        return ret

def download(bucket, key):
    print("Downloading {}".format(key))
    tmpkey = key.replace("/", "")
    tmpkey = tmpkey.replace(" ", "_")
    tmp_path = "/tmp/{}{}".format(uuid.uuid4(), tmpkey)
    s3.download_file(bucket, key, tmp_path)
    return tmp_path

def process_image(md, config):
    tmp_path = download(md["Bucket"], md["Key"])
    exif_data = get_exif_data(tmp_path)
    md = enrich_meta_data(md, exif_data, config)
    save_image(md, config)

def validate(file_name):
    ext = os.path.splitext(file_name)
    if ext[1].lower() not in SUPPORTED_FILE_TYPES:
        return False
    return True

def getConfig(context, ssm_names=SSM_NAMES):
    ret = {}
    for key, value in ssm_names.items():
        try:
            ret[key] = getattr(context,"config").get(value)
            if ret[key] is None:
                raise ValueError(value)
        except ValueError as err:
            print("SSN name '{}' was not found".format(err))
        except:
            print("An error occured fetching remote config")
    return ret

@ssm.cache(
  parameter=[value for _, value in SSM_NAMES.items()],
  entry_name="config",
  max_age_in_seconds=300
)
def handler(event, context):
    print('event: {}'.format(event))
    config = getConfig(context)
    for record in event["Records"]:
        md = {
          "Bucket": record["s3"]["bucket"]["name"],
          "Key": unquote_plus(record["s3"]["object"]["key"]),
        }
        print("New file detected in {}: {}".format(md["Bucket"], md["Key"]))
        md["FileName"] = ntpath.basename(md["Key"])
        if validate(md["FileName"]):
          process_image(md, config)
        else:
            print("{} is not a supported file type".format(md["FileName"]))
        print("Deleting {} from {}".format(md["Key"], md["Bucket"]))
        s3.delete_object(Bucket=md["Bucket"], Key=md["Key"])