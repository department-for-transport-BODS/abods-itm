import json
import time

import boto3
import cfnresponse

session = boto3.session.Session()
sns = session.client("sns")
sqs = session.client("sqs")


def check_subscription_status(topic_arn, queue_arn):  # noqa: ANN001, ANN201 - BODS-7131
    """
    Queries the SNS queue for existing subscriptions to determine the status of pre-existing subscriptions.
    """  # noqa: D200, D401 - BODS-7131
    response = sns.list_subscriptions_by_topic(TopicArn=topic_arn)

    for subscription in response["Subscriptions"]:
        if subscription["Endpoint"] == queue_arn:
            return subscription["SubscriptionArn"], subscription[
                "SubscriptionArn"
            ].startswith("arn:")

    return None, False


def confirm_subscription(  # noqa: ANN201 - BODS-7131
    topic_arn,  # noqa: ANN001 - BODS-7131
    queue_arn,  # noqa: ANN001 - BODS-7131
    queue_url,  # noqa: ANN001 - BODS-7131
    timeout_seconds=180,  # noqa: ANN001 - BODS-7131
    poll_interval=10,  # noqa: ANN001 - BODS-7131
):
    """
    Polls the SQS queue to find and confirm the subscription confirmation message.
    """  # noqa: D200, D401 - BODS-7131
    subscription_arn, is_confirmed = check_subscription_status(topic_arn, queue_arn)

    if not is_confirmed:
        end_time = time.time() + timeout_seconds
        while time.time() < end_time:
            messages = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=poll_interval,
            ).get("Messages", [])

            for message in messages:
                body = json.loads(message["Body"])
                if (
                    body["Type"] == "SubscriptionConfirmation"
                    and body["TopicArn"] == topic_arn
                ):
                    sns.confirm_subscription(TopicArn=topic_arn, Token=body["Token"])
                    sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    )
                    return True
            time.sleep(poll_interval)
        return False
    return True


def lambda_handler(event, context):  # noqa: ANN001, ANN201 - BODS-7131
    request_type = event["RequestType"]
    props = event["ResourceProperties"]

    sns_topic_arn = props.get("SnsTopicArn", None)
    sqs_queue_arn = props.get("SqsQueueArn", None)
    sqs_queue_url = props.get("SqsQueueUrl", None)

    try:
        if request_type in ["Create", "Update"]:
            response = sns.subscribe(
                TopicArn=sns_topic_arn,
                Protocol="sqs",
                Endpoint=sqs_queue_arn,
            )
            subscription_arn = response["SubscriptionArn"]

            if request_type == "Create":
                confirmation_received = confirm_subscription(
                    sns_topic_arn,
                    sqs_queue_arn,
                    sqs_queue_url,
                )
                if not confirmation_received:
                    raise TimeoutError(  # noqa: TRY301 - BODS-7131
                        "Subscription confirmation not received in time.",
                    )

            cfnresponse.send(
                event,
                context,
                cfnresponse.SUCCESS,
                {"SubscriptionArn": subscription_arn},
                subscription_arn,
            )
        elif request_type == "Delete":
            subscription_arn = event["PhysicalResourceId"]
            sns.unsubscribe(SubscriptionArn=subscription_arn)

            cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, subscription_arn)
    except Exception as e:  # noqa: BLE001 - BODS-7131
        print(e)  # noqa: T201 - BODS-7131
        cfnresponse.send(
            event,
            context,
            cfnresponse.FAILED,
            {},
            context.log_stream_name,
        )
