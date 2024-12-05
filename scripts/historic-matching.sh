#!/bin/bash

set -euo pipefail

PROJECT_NAME="abods"
ENVIRONMENT="sandbox"

PRIVATE_SUBNET_IDS=$(aws ssm get-parameter --name /abods/$ENVIRONMENT/vpc/subnets/private --output text --query Parameter.Value)
VPC_SG_IDS=$(aws ssm get-parameter --name /abods/$ENVIRONMENT/ec2/securitygroup/rdsproxy-access/id --output text --query Parameter.Value)

TASK_ID=$(aws ecs run-task --cluster "$PROJECT_NAME-$ENVIRONMENT" --task-definition "$PROJECT_NAME-$ENVIRONMENT-historic-matching" --count 1 --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNET_IDS],securityGroups=[$VPC_SG_IDS]}" | jq -r '.tasks.[0].taskArn' | cut -d "/" -f 3)

python3 -m webbrowser "https://eu-west-2.console.aws.amazon.com/ecs/v2/clusters/abods-$ENVIRONMENT/tasks/$TASK_ID/logs?region=eu-west-2"
