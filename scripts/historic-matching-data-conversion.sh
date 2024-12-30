#!/bin/bash

set -euo pipefail

if [ $# -lt 2 ]
  then
    echo "Usage: $0 <process_date YYYY-MM-DD> <environment sandbox|dev|test|uat|prod>"
    exit
fi

PROCESS_DATE=$1
ENVIRONMENT="$2"
PROJECT_NAME="abods"

# Options
SKIP_AVL="false"
SKIP_TIMETABLE="false"
OVERWRITE_EXISTING_OUTPUT="false"

aws lambda invoke --function-name "$PROJECT_NAME-$ENVIRONMENT-convert-to-parquet-function" --cli-binary-format raw-in-base64-out --payload "{\"process_date\":\"$PROCESS_DATE\",\"skip_timetable\":\"$SKIP_TIMETABLE\",\"skip_avl\":\"$SKIP_AVL\",\"overwrite_existing_output\":\"$OVERWRITE_EXISTING_OUTPUT\"}" /dev/stdout
