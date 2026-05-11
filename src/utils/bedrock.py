"""Utility for invoking Amazon Bedrock models via the Converse API."""

import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# Full Inference Profile ARN — update this if you switch profiles or accounts.
MODEL_ID = (
    "arn:aws:bedrock:us-east-1:300923420347:"
    "inference-profile/us.amazon.nova-lite-v1:0"
)

# Bedrock region must match the inference profile's home region.
AWS_REGION = "us-east-1"


def _get_client():
    """Return a Bedrock Runtime client pinned to us-east-1.

    Credentials are resolved from the standard boto3 chain:
    environment variables → ~/.aws/credentials → IAM role.
    """
    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


def invoke_agent(system_prompt: str, user_content: str) -> str:
    """Call the Bedrock Converse API and return the assistant's text response.

    Uses the Inference Profile ARN defined in MODEL_ID with the Nova-specific
    inference configuration required by the profile.

    Args:
        system_prompt: Instructions that define the agent's role and behaviour.
        user_content:  The user-facing message or task description.

    Returns:
        The model's text response as a plain string.

    Raises:
        RuntimeError: Wraps any Bedrock / network error with a human-readable
                      message so LangGraph nodes receive a clean exception.
    """
    client = _get_client()

    request: dict = {
        "modelId": MODEL_ID,
        "system": [{"text": system_prompt}],
        "messages": [
            {
                "role": "user",
                "content": [{"text": user_content}],
            }
        ],
        # Nova inference profile configuration
        "inferenceConfig": {
            "maxTokens": 512,
            "temperature": 0.7,
            "topP": 0.9,
        },
        # Required by the Nova inference profile; pass empty dict for defaults.
        "additionalModelRequestFields": {},
        # Request standard (vs. optimised) latency tier.
        "performanceConfig": {"latency": "standard"},
    }

    try:
        response = client.converse(**request)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        error_msg = exc.response["Error"]["Message"]
        logger.error("Bedrock ClientError [%s]: %s", error_code, error_msg)

        if error_code == "ValidationException":
            raise RuntimeError(
                f"Bedrock ValidationException: {error_msg}\n"
                "Hint: verify that MODEL_ID is a valid Inference Profile ARN "
                "and that your IAM role has 'bedrock:InvokeModel' permission "
                f"for the profile in {AWS_REGION}."
            ) from exc

        raise RuntimeError(
            f"Bedrock request failed ({error_code}): {error_msg}"
        ) from exc
    except BotoCoreError as exc:
        logger.error("BotoCoreError calling Bedrock: %s", exc)
        raise RuntimeError(f"Bedrock connection error: {exc}") from exc

    return _extract_text(response)


def _extract_text(response: dict) -> str:
    """Pull the assistant's text out of a Converse API response.

    The Converse response shape is:
        response["output"]["message"]["content"] -> list of content blocks
    Each block may be {"text": "..."} or other types (image, tool use, etc.).
    We concatenate all text blocks and return a single string.
    """
    try:
        content_blocks: list = response["output"]["message"]["content"]
        text_parts: list[str] = [
            block["text"]
            for block in content_blocks
            if "text" in block
        ]
        result = "\n".join(text_parts).strip()
        if not result:
            raise ValueError("Model returned no text content.")
        return result
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("Unexpected Bedrock response structure: %s", response)
        raise RuntimeError(
            f"Could not parse Bedrock response: {exc}"
        ) from exc
