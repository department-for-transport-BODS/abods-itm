#!/bin/bash
set -euo pipefail

if [ $# -lt 2 ]
  then
    echo "Usage: $0 <process_date YYYY-MM-DD> <environment sandbox|dev|test|uat|prod>"
    exit
fi

PROCESS_DATE="$1"
ENVIRONMENT="$2"
PROJECT_NAME="abods"
DEBUG_GROUP_IDS=""

PRIVATE_SUBNET_IDS=$(aws ssm get-parameter --name "/$PROJECT_NAME/$ENVIRONMENT/vpc/subnets/private" --output text --query Parameter.Value)
VPC_SG_IDS=$(aws ssm get-parameter --name "/$PROJECT_NAME/$ENVIRONMENT/ec2/securitygroup/rdsproxy-access/id" --output text --query Parameter.Value)

TASK_ID=$(aws ecs run-task --cluster "$PROJECT_NAME-$ENVIRONMENT" --task-definition "$PROJECT_NAME-$ENVIRONMENT-historic-matching" --overrides "{ \"containerOverrides\": [ { \"name\": \"matcher\", \"environment\": [ { \"name\": \"PROCESS_DATE\", \"value\": \"$PROCESS_DATE\" }, { \"name\": \"SIRIVM_BUCKET\", \"value\": \"abods-$ENVIRONMENT-exporter-bucket\" }, { \"name\": \"DEBUG_GROUP_IDS\", \"value\": \"$DEBUG_GROUP_IDS\" } ] } ] }" --count 1 --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNET_IDS],securityGroups=[$VPC_SG_IDS]}" | jq -r '.tasks.[0].taskArn' | cut -d "/" -f 3)

ecs_logs_link="https://eu-west-2.console.aws.amazon.com/ecs/v2/clusters/$PROJECT_NAME-$ENVIRONMENT/tasks/$TASK_ID/logs?region=eu-west-2"

echo "You can read the logs at $ecs_logs_link"

python3 -m webbrowser "$ecs_logs_link"
