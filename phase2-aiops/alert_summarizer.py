"""
Alert Summarizer — Part 1
=========================
Parses Prometheus and Dynatrace alert payloads.
Sends to Gemini for AI enrichment.
Returns structured diagnosis ready for Slack.

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 6
"""

import json
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ─────────────────────────────────────────
# SAMPLE ALERT PAYLOADS
# These simulate real alerts from Prometheus
# and Dynatrace — the tools you use at JPMC
# ─────────────────────────────────────────
SAMPLE_ALERTS = {

    "high_cpu": {
        "alertname": "HighCPUUsage",
        "severity": "critical",
        "status": "firing",
        "labels": {
            "env": "production",
            "service": "payment-api",
            "team": "payments",
            "namespace": "production"
        },
        "annotations": {
            "description": "CPU usage above 90% for last 5 minutes on payment-api",
            "current_value": "94%",
            "threshold": "90%"
        },
        "startsAt": "2025-04-01T03:22:00Z"
    },

    "pod_restart": {
        "alertname": "PodRestartingFrequently",
        "severity": "warning",
        "status": "firing",
        "labels": {
            "env": "production",
            "pod": "order-service-6c8d9f-mn4kl",
            "namespace": "production",
            "service": "order-service"
        },
        "annotations": {
            "description": "Pod has restarted 8 times in last 30 minutes",
            "restart_count": "8",
            "last_exit_code": "1"
        },
        "startsAt": "2025-04-01T02:15:00Z"
    },

    "high_memory": {
        "alertname": "HighMemoryUsage",
        "severity": "critical",
        "status": "firing",
        "labels": {
            "env": "production",
            "service": "fraud-detection",
            "namespace": "ml-services",
            "node": "ip-10-0-1-45"
        },
        "annotations": {
            "description": "Memory usage at 87% of limit on fraud-detection service",
            "current_value": "445Mi",
            "limit": "512Mi"
        },
        "startsAt": "2025-04-01T04:01:00Z"
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
# Pulls the most important fields out of
# the raw alert JSON dictionary
# Handles missing fields gracefully
# ─────────────────────────────────────────
def extract_alert_fields(alert):
    """
    Extracts key fields from a raw alert payload.
    Works with both Prometheus and Dynatrace formats.
    Returns a clean flat dictionary.
    """
    # .get() safely returns empty string if field missing
    # Nested .get() handles nested dicts like labels{}
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
# Builds engineered prompt using extracted
# alert fields — uses few-shot technique
# ─────────────────────────────────────────
def build_alert_prompt(fields):
    """
    Builds a structured prompt from alert fields.
    Uses few-shot examples for consistent JSON output.
    """
    return f"""
You are a senior SRE on-call engineer at a fintech company.
Analyze the alert below and return ONLY valid JSON.

Here is an example of correct output format:

Alert: HighCPUUsage on payment-api in production, CPU at 94%
Output: {{
  "alert_name": "HighCPUUsage",
  "severity": "P1",
  "affected_service": "payment-api",
  "environment": "production",
  "summary": "payment-api CPU usage at 94%, exceeding 90% threshold for 5 minutes",
  "probable_cause": "Traffic spike or memory leak causing excessive CPU consumption",
  "immediate_steps": [
    "kubectl top pods -n production | grep payment-api",
    "kubectl logs payment-api-xxx -n production --tail=100",
    "Check Grafana dashboard for traffic spike correlation"
  ],
  "escalate": true,
  "escalate_reason": "Production service degradation affecting payments"
}}

Now analyze this alert. Return JSON only. No text before or after.

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
- immediate_steps must have exactly 3 kubectl or monitoring commands
- escalate must be true if severity is P1 or service is down
- All fields must be present — use "unknown" if not determinable
"""


# ─────────────────────────────────────────
# FUNCTION 3: call_gemini
# Sends prompt to Gemini, cleans response,
# parses and returns JSON dictionary
# ─────────────────────────────────────────
def call_gemini(prompt):
    """
    Sends prompt to Gemini API.
    Cleans response and parses JSON.
    Returns parsed dictionary or None on failure.
    """
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
        print(f"Raw response: {response.text[:200]}")
        return None


# ─────────────────────────────────────────
# FUNCTION 4: format_console_output
# Prints the diagnosis in a clean readable
# format to your terminal
# ─────────────────────────────────────────
def format_console_output(result, alert_name):
    """
    Prints enriched alert diagnosis to terminal.
    Formatted for easy reading during development.
    """
    severity = result.get("severity", "P3")

    # Emoji based on severity — visual triage at a glance
    emoji = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}.get(severity, "⚪")

    print(f"\n{'='*60}")
    print(f"{emoji}  {severity} — {result.get('alert_name', alert_name)}")
    print(f"{'='*60}")
    print(f"Service     : {result.get('affected_service', 'unknown')}")
    print(f"Environment : {result.get('environment', 'unknown')}")
    print(f"Summary     : {result.get('summary', 'unknown')}")
    print(f"\nProbable Cause:")
    print(f"  {result.get('probable_cause', 'unknown')}")
    print(f"\nImmediate Steps:")
    steps = result.get("immediate_steps", [])
    for i, step in enumerate(steps, 1):
        print(f"  {i}. {step}")
    print(f"\nEscalate    : {result.get('escalate', False)}")
    if result.get("escalate"):
        print(f"Reason      : {result.get('escalate_reason', 'unknown')}")


# ─────────────────────────────────────────
# FUNCTION 5: summarize_alert
# Main function — orchestrates the full flow
# extract → prompt → Gemini → format output
# ─────────────────────────────────────────
def summarize_alert(alert, alert_name="unknown"):
    """
    Main function. Takes raw alert dict.
    Returns enriched diagnosis dict.
    """
    # Step 1: Extract clean fields from raw alert
    fields = extract_alert_fields(alert)

    # Step 2: Build engineered prompt
    prompt = build_alert_prompt(fields)

    # Step 3: Send to Gemini
    result = call_gemini(prompt)

    if result:
        # Step 4: Print formatted output
        format_console_output(result, alert_name)
        return result
    else:
        print(f"Failed to analyze alert: {alert_name}")
        return None


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("🚨 Alert Summarizer — Starting")
    print("Processing 4 sample alerts...\n")

    results = {}

    for alert_name, alert_payload in SAMPLE_ALERTS.items():
        result = summarize_alert(alert_payload, alert_name)
        if result:
            results[alert_name] = result

    print(f"\n{'='*60}")
    print(f"✅ Processed {len(results)}/4 alerts successfully")
    print(f"Day 7: These results will be posted to Slack automatically")
    print(f"{'='*60}")