#!/bin/bash

rm -f package.zip
zip package.zip *.py
cd lib/python3.6/site-packages
zip -x "./boto3*" -x "./botocore*" -x "./jmespath*" -x "./python_dateutil*" -x "./dateutil*" -x "./s3transfer*" -r ../../../package.zip ./*
cd ../../../
