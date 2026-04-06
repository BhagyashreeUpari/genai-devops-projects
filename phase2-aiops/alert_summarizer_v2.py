"""
Alert Summarizer v2 — With Slack Integration
=============================================
Complete AIOps alert pipeline:
  1. Receives alert payload (Prometheus/Dynatrace format)
  2. Extracts fields defensively
  3. Sends to Gemini for AI enrichment
  4. Posts colour-coded enriched alert to Slack

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 7
"""

import json
import requests
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

# Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Slack webhook URL from .env
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")


# ─────────────────────────────────────────
# SAMPLE ALERTS — same as Day 6
# ─────────────────────────────────────────
SAMPLE_ALERTS = {

    "high_cpu": {
        "alertname": "HighCPUUsage",
        "severity": "critical",
        "status": "firing",
        "labels": {
            "env": "production",
            "service": "payment-api",
            "namespace": "production"
        },
        "annotations": {
            "description": "CPU usage above 90% for last 5 minutes on payment-api",
            "current_value": "94%",
            "threshold": "90%"
        },
        "startsAt": "2025-04-01T03:22:00Z"
    },

    "service_down": {
        "alertname": "ServiceUnavailable",
        "severity": "critical",
        "status": "firing",
        "labels": {
            "env": "production",
            "service": "auth-service",
            "namespace": "production",
            "team": "platform"
        },
        "annotations": {
            "description": "auth-service has 0 healthy pods for last 2 minutes",
            "healthy_pods": "0",
            "desired_pods": "3"
        },
        "startsAt": "2025-04-01T03:55:00Z"
    }
}


# ─────────────────────────────────────────
# FUNCTION 1: extract_alert_fields
# Same defensive extraction from Day 6
# ─────────────────────────────────────────
def extract_alert_fields(alert):
    """Extracts key fields from raw alert payload."""
    return {
        "alertname":   alert.get("alertname", "unknown"),
        "severity":    alert.get("severity", "unknown"),
        "status":      alert.get("status", "unknown"),
        "service":     alert.get("labels", {}).get("service", "unknown"),
        "environment": alert.get("labels", {}).get("env", "unknown"),
        "namespace":   alert.get("labels", {}).get("namespace", "unknown"),
        "description": alert.get("annotations", {}).get("description", "unknown"),
        "started_at":  alert.get("startsAt", "unknown"),
    }


# ─────────────────────────────────────────
# FUNCTION 2: build_alert_prompt
# Same engineered prompt from Day 6
# ─────────────────────────────────────────
def build_alert_prompt(fields):
    """Builds engineered few-shot prompt from alert fields."""
    return f"""
You are a senior SRE on-call engineer at a fintech company.
Analyze the alert below and return ONLY valid JSON.

Example output format:
{{
  "alert_name": "HighCPUUsage",
  "severity": "P1",
  "affected_service": "payment-api",
  "environment": "production",
  "summary": "payment-api CPU at 94%, exceeding 90% threshold for 5 minutes",
  "probable_cause": "Traffic spike or memory leak causing CPU exhaustion",
  "immediate_steps": [
    "kubectl top pods -n production | grep payment-api",
    "kubectl logs payment-api-xxx -n production --tail=100",
    "Check Grafana dashboard for traffic spike correlation"
  ],
  "escalate": true,
  "escalate_reason": "Production payment service degradation"
}}

Alert details:
- Alert Name  : {fields['alertname']}
- Severity    : {fields['severity']}
- Service     : {fields['service']}
- Environment : {fields['environment']}
- Namespace   : {fields['namespace']}
- Description : {fields['description']}
- Started At  : {fields['started_at']}

Rules:
- severity must be P1, P2 or P3
- immediate_steps must have exactly 3 commands
- escalate must be true if severity is P1
- Return JSON only. No text before or after.
"""


# ─────────────────────────────────────────
# FUNCTION 3: call_gemini
# Same Gemini call from Day 6
# ─────────────────────────────────────────
def call_gemini(prompt):
    """Sends prompt to Gemini, returns parsed JSON or None."""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a senior SRE engineer. "
                "Always return valid JSON only. "
                "No markdown. No explanation outside JSON."
            ),
            temperature=0,
        ),
        contents=prompt
    )
    try:
        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        return None


# ─────────────────────────────────────────
# FUNCTION 4: build_slack_message
# Builds a rich Slack Block Kit message
# Colour coded by severity
# ─────────────────────────────────────────
def build_slack_message(result):
    """
    Builds a Slack Block Kit message from enriched alert.
    Uses colour-coded attachments:
      Red    = P1 Critical
      Yellow = P2 Warning
      Green  = P3 Info
    """
    severity = result.get("severity", "P3")

    # Colour hex codes for Slack attachments
    # These appear as a coloured bar on the left of the message
    colors = {
        "P1": "#FF0000",  # Red — critical
        "P2": "#FFA500",  # Orange — warning
        "P3": "#36A64F",  # Green — informational
    }
    color = colors.get(severity, "#808080")

    # Severity emoji for visual triage
    emojis = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}
    emoji = emojis.get(severity, "⚪")

    # Format immediate steps as numbered list
    # Slack uses \n for newlines inside text blocks
    steps = result.get("immediate_steps", [])
    steps_text = "\n".join(
        f"{i+1}. `{step}`" for i, step in enumerate(steps)
    )

    # Build Slack Block Kit message
    # attachments = array of message cards
    # blocks = sections within each card
    # mrkdwn = Slack markdown (*bold*, `code`, etc)
    slack_message = {
        "attachments": [
            {
                "color": color,
                "blocks": [
                    {
                        # Header section — alert name and severity
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"{emoji} *{severity} — "
                                f"{result.get('alert_name', 'Unknown Alert')}*\n"
                                f"*Service:* {result.get('affected_service','unknown')} "
                                f"| *Env:* {result.get('environment','unknown')}"
                            )
                        }
                    },
                    {"type": "divider"},
                    {
                        # Summary section
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*Summary:*\n{result.get('summary','unknown')}\n\n"
                                f"*Probable Cause:*\n"
                                f"{result.get('probable_cause','unknown')}"
                            )
                        }
                    },
                    {"type": "divider"},
                    {
                        # Immediate steps section
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Immediate Investigation Steps:*\n{steps_text}"
                        }
                    },
                ]
            }
        ]
    }

    # Add escalation block if escalation needed
    if result.get("escalate"):
        slack_message["attachments"][0]["blocks"].append(
            {"type": "divider"}
        )
        slack_message["attachments"][0]["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"⚠️ *ESCALATION REQUIRED*\n"
                    f"{result.get('escalate_reason','Escalate immediately')}"
                )
            }
        })

    return slack_message


# ─────────────────────────────────────────
# FUNCTION 5: post_to_slack
# POSTs the message to Slack webhook URL
# Uses requests library
# ─────────────────────────────────────────
def post_to_slack(slack_message):
    """
    Posts message to Slack via incoming webhook.
    Returns True if successful, False if failed.
    """
    if not SLACK_WEBHOOK_URL:
        print("SLACK_WEBHOOK_URL not set in .env file")
        return False

    # requests.post sends HTTP POST request
    # json= parameter automatically serializes dict to JSON
    # and sets Content-Type: application/json header
    response = requests.post(
        url=SLACK_WEBHOOK_URL,
        json=slack_message
    )

    # HTTP 200 = success
    # Slack returns plain text "ok" on success
    if response.status_code == 200:
        print("Posted to Slack successfully")
        return True
    else:
        print(f"Slack post failed: {response.status_code} — {response.text}")
        return False


# ─────────────────────────────────────────
# FUNCTION 6: process_alert
# Main orchestrator — full pipeline
# extract → prompt → gemini → slack
# ─────────────────────────────────────────
def process_alert(alert, alert_name="unknown"):
    """
    Full alert processing pipeline.
    Returns enriched result dict or None.
    """
    print(f"\nProcessing: {alert_name}")

    # Step 1: Extract fields
    fields = extract_alert_fields(alert)

    # Step 2: Build prompt
    prompt = build_alert_prompt(fields)

    # Step 3: Call Gemini
    result = call_gemini(prompt)

    if not result:
        print(f"Gemini analysis failed for {alert_name}")
        return None

    # Step 4: Build Slack message
    slack_message = build_slack_message(result)

    # Step 5: Post to Slack
    posted = post_to_slack(slack_message)

    if posted:
        print(f"Alert {alert_name} — fully processed and posted to Slack")
    else:
        print(f"Alert {alert_name} — processed but Slack post failed")

    return result


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("Alert Summarizer v2 — Starting")
    print("Pipeline: Alert → Gemini → Slack\n")

    # Check Slack webhook is configured
    if not SLACK_WEBHOOK_URL:
        print("ERROR: Add SLACK_WEBHOOK_URL to your .env file first")
        exit(1)

    results = {}

    for alert_name, alert_payload in SAMPLE_ALERTS.items():
        result = process_alert(alert_payload, alert_name)
        if result:
            results[alert_name] = result

    print(f"\nDone. Processed {len(results)}/2 alerts.")
    print("Check your #alerts Slack channel!")