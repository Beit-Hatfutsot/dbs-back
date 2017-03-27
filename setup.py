#!/usr/bin/env python
from setuptools import setup, find_packages
import os
import time


if os.path.exists("VERSION.txt"):
    # this file can be written by CI tools (e.g. Travis) to specify the published version
    with open("VERSION.txt") as version_file:
        version = version_file.read().strip().strip("v")
else:
    # if version is not specified - we use the current timestamp to ensure module is updated
    version = str(time.time())

setup(
    name='bh-dbs-back',
    version=version,
    packages=find_packages(exclude=["tests", "test.*"])
)
