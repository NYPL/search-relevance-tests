import hashlib
import hmac
import json
import os

from nypl_py_utils.functions.log_helper import create_log

logger = create_log("lambda")


class WebhookException(Exception):
    pass


def verify_webhook_signature(payload_body, secret_token, signature_header):
    """
    Verify that the payload was sent from GitHub by validating SHA256.

    Raise and return 403 if not authorized.
    """
    if not signature_header:
        logger.debug("Webhook sig missing")
        raise WebhookException("x-hub-signature-256 header is missing!")
    hash_object = hmac.new(
        secret_token.encode("utf-8"),
        msg=payload_body.encode("utf-8"),
        digestmod=hashlib.sha256,
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    if not hmac.compare_digest(expected_signature, signature_header):
        logger.debug("Webhook sig invalid")
        raise WebhookException("Request signatures didn't match!")
    logger.debug("Webhook sig verified")


def validate_webhook(event):
    sig_header = event["headers"].get("x-hub-signature-256")
    verify_webhook_signature(
        event["body"], os.environ.get("WEBHOOK_SECRET"), sig_header
    )

    body = json.loads(event["body"])
    try:
        body["repository"]["name"]
    except Exception:
        raise WebhookException("Repository name not found")


def lambda_error(status, error):
    return {"statusCode": status, "message": str(error)}
