# settings.py
from os.path import join, dirname
from dotenv import load_dotenv
import os

dotenv_path = join(dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path)

S3_BUCKET_PREFIX=os.environ["S3_BUCKET_PREFIX"]
AWS_ACCESS_KEY_ID=os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY=os.environ["AWS_SECRET_ACCESS_KEY"]
S3_ENDPOINT_URL=os.environ["S3_ENDPOINT_URL"]
SITEMAP_ES_HOST=os.environ["SITEMAP_ES_HOST"]
SITEMAP_ES_INDEX=os.environ["SITEMAP_ES_INDEX"]
