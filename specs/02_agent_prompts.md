# Spec 02: Agent Prompts

## Goal

Define the roles of your four agents.

## Content for Kiro

Create a `prompts.py` file containing system messages for:

- **Compliance Sentinel**: Legal expert focused on GDPR/APPI. Must identify data residency risks.
- **Cultural Strategist**: Marketing expert. Must adapt US rewards to local currency and psychology.
- **Technical Architect**: Senior Engineer. Must generate clean, commented SQL (Snowflake) and Python (Lambda).
- **QA Validator**: Code auditor. Must cross-reference the Architect's code against the Compliance risks.
