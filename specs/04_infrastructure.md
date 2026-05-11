# Spec 04: Infrastructure

## Goal

Connect to the AWS Bedrock "Pipes."

## Content for Kiro

Create a utility in `utils/bedrock.py` using Boto3 Converse API.

- **Model:** `amazon.nova-premier-v1:0`
- **Function:** `invoke_agent(system_prompt, user_content)`
- Handle internal Bedrock errors and provide clean string outputs for the LangGraph nodes.


you can use Lang Graph and AWS MCP server to fetch additional data.