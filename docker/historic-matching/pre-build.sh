#!/bin/bash

cp -r ../../ingestion_pipelines/sirivm_otp_matching_function ./files
rm -rf ./files/sirivm_otp_matching_function/shared
cp -r ../../shared ./files/sirivm_otp_matching_function/shared
