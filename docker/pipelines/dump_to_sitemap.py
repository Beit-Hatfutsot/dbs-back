from datapackage_pipelines.wrapper import ingest, spew
from botocore.client import Config
from botocore.exceptions import ClientError
from temp_loglevel import temp_loglevel
from temp_files import temp_file
import settings
import urllib.parse
import logging
import json
import datetime
import boto3


def get_urls_from_row(row):
    global stats
    for lang in ["He", "En"]:
        slug = row.get("Slug_{}".format(lang))
        if slug and len(slug) > 3 and "_" in slug:
            if slug.startswith("person"):
                if lang != "En":
                    continue
                stats["person docs"] += 1
                url = slug.replace('_', '/').replace(';', '/').replace('.', '/')
            else:
                slug = slug.split("_")
                if lang == "He":
                    url = "he/{}/{}".format(slug[1], slug[0])
                else:
                    url = "{}/{}".format(slug[0], slug[1])
            url = urllib.parse.quote(url)
            url = "https://dbs.bh.org.il/{}".format(url)
            yield url


def get_urls(resource):
    for path in parameters["paths"]:
        yield "https://dbs.bh.org.il{}".format(path)
    for row in resource:
        yield from get_urls_from_row(row)


def dump_urls_to_sitemap(urls_generator, object_name):
    has_more, size, urls = False, 0, 0
    with temp_file() as temp_filename:
        logging.info("writing to temp filename {}".format(temp_filename))
        with open(temp_filename, "w") as f:
            for url in urls_generator:
                line = "{}\n".format(url)
                f.write(line)
                urls += 1
                size += len(line)
                if size % 1024*1024 == 0:
                    logging.info("wrote {} urls, {} bytes".format(urls, size))
                if urls >= parameters["max-urls-per-page"]:
                    logging.info("reached max urls per page ({})".format(parameters["max-urls-per-page"]))
                    has_more = True
                    break
                elif size >= parameters["max-file-size-bytes"]:
                    logging.info("reached max file size ({})".format(parameters["max-file-size-bytes"]))
                    has_more = True
                    break
        logging.info("writing from temp file to object {}".format(object_name))
        with temp_loglevel():
            s3.Object(bucket_name, object_name).upload_file(temp_filename)
    return has_more, size, urls


def object_name_to_url(object_name):
    return "https://dbs.bh.org.il/sitemap/{}".format(object_name)


def filter_resource(resource):
    global stats
    logging.info("using bucket: {}".format(bucket))
    try:
        with temp_loglevel():
            bucket.create()
    except ClientError as e:
        if e.response['Error']['Code'] not in ['BucketAlreadyOwnedByYou']:
            raise
    with temp_loglevel():
        s3.BucketPolicy(bucket_name).put(Policy=json.dumps({"Version": str(datetime.datetime.now()).replace(" ", "-"),
                                                            "Statement": [{"Sid": "AddPerm",
                                                                           "Effect": "Allow",
                                                                           "Principal": {"AWS": ["*"]},
                                                                           "Action": ["s3:GetObject"],
                                                                           "Resource": ["arn:aws:s3:::{}/*".format(bucket_name)]}]}))
    urls_generator = get_urls(resource)
    index = []
    while True:
        if len(index) == 0:
            object_name = "sitemap.txt"
        else:
            object_name = "sitemap-{}.txt".format(len(index)+1)
        index.append({"size": 0, "urls": 0, "object_name": object_name})
        has_more, index[-1]["size"], index[-1]["urls"] = dump_urls_to_sitemap(urls_generator, index[-1]["object_name"])
        yield index[-1]
        if not has_more:
            break
    if len(index) >= parameters["max-urls-per-page"]:
        raise Exception("There is a hard limit of {} sitemaps per sitemap index".format(parameters["max-urls-per-page"]))
    with temp_file() as temp_filename:
        size = 0
        with open(temp_filename, "w") as f:
            lines = '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            size += len(lines)
            f.write(lines)
            last_lines = '</sitemapindex>'
            len_last_lines = len(last_lines)
            for page in index:
                lines = '<sitemap><loc>{}</loc></sitemap>\n'.format(object_name_to_url(page["object_name"]))
                size += len(lines)
                if size+len_last_lines >= parameters["max-file-size-bytes"]:
                    raise Exception("There is a hard limit of {} bytes per sitemap index file".format(parameters["max-file-size-bytes"]))
                f.write(lines)
                stats["{}_urls".format(page["object_name"])] = page["urls"]
                stats["{}_size".format(page["object_name"])] = page["size"]
            f.write(last_lines)
        with temp_loglevel():
            s3.Object(bucket_name, "sitemap.xml").upload_file(temp_filename)


def get_resources():
    global resources
    for resource in resources:
        yield filter_resource(resource)


if __name__ == "__main__":
    parameters, datapackage, resources = ingest()
    stats = {}
    s3 = boto3.resource('s3', endpoint_url=settings.S3_ENDPOINT_URL,
                        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                        config=Config(signature_version='s3v4'), region_name='us-east-1')
    bucket_name = "{}{}".format(settings.S3_BUCKET_PREFIX, "sitemap")
    bucket = s3.Bucket(bucket_name)
    datapackage["resources"][0]["schema"]["fields"] = [{"name": "urls", "type": "number"},
                                                       {"name": "size", "type": "number"},
                                                       {"name": "object_name", "type": "string"}]
    spew(datapackage, get_resources(), stats)
