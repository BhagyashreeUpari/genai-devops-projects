"""
Dynatrace Alert Handler
========================
Processes Dynatrace problem notifications
using AI enrichment.

Dynatrace uses 'Problems' not just alerts —
a Problem groups related symptoms with root
cause already identified by Davis AI.

Your tool adds a second AI layer on top of
Davis AI for human-readable diagnosis and
actionable steps.

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 12
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─────────────────────────────────────────
# DYNATRACE SEVERITY MAPPING
# Maps Dynatrace severity to P1/P2/P3
# ─────────────────────────────────────────
SEVERITY_MAP = {
    "AVAILABILITY":        "P1",
    "ERROR":               "P1",
    "PERFORMANCE":         "P2",
    "RESOURCE_CONTENTION": "P2",
    "CUSTOM_ALERT":        "P3",
}


# ─────────────────────────────────────────
# SAMPLE DYNATRACE PROBLEM NOTIFICATIONS
# These mirror real Dynatrace webhook payloads
# Similar to what fires at JPMC
# ─────────────────────────────────────────
DYNATRACE_PROBLEMS = {

    "payment_api_slowdown": {
        "problemId": "P-20250401-001",
        "problemTitle": "Response time degradation on payment-api",
        "state": "OPEN",
        "severity": "PERFORMANCE",
        "impactLevel": "APPLICATION",
        "affectedEntities": [
            {"entityId": "SERVICE-PAY001", "name": "payment-api"},
            {"entityId": "SERVICE-AUTH001", "name": "auth-service"},
        ],
        "rootCauseEntity": {
            "entityId": "SERVICE-DB001",
            "name": "payments-db"
        },
        "events": [
            {
                "eventType": "SLOW_QUERY",
                "description": "Average query time increased from 45ms to 890ms"
            },
            {
                "eventType": "RESPONSE_TIME_DEGRADED",
                "description": "payment-api p99 latency exceeded 500ms threshold"
            }
        ],
        "tags": ["payment-api", "production", "critical-path"],
        "impactedUsers": 1247,
        "startTime": "2025-04-01T03:15:00Z"
    },

    "auth_service_down": {
        "problemId": "P-20250401-002",
        "problemTitle": "Availability issue on auth-service",
        "state": "OPEN",
        "severity": "AVAILABILITY",
        "impactLevel": "SERVICE",
        "affectedEntities": [
            {"entityId": "SERVICE-AUTH001", "name": "auth-service"},
            {"entityId": "SERVICE-API001", "name": "api-gateway"},
        ],
        "rootCauseEntity": {
            "entityId": "HOST-NODE002",
            "name": "ip-10-0-1-45"
        },
        "events": [
            {
                "eventType": "HOST_OF_SERVICE_UNAVAILABLE",
                "description": "Node ip-10-0-1-45 became unavailable"
            },
            {
                "eventType": "SERVICE_UNAVAILABLE",
                "description": "auth-service has 0 healthy instances"
            }
        ],
        "tags": ["auth-service", "production", "slo-critical"],
        "impactedUsers": 5420,
        "startTime": "2025-04-01T03:55:00Z"
    },

    "fraud_detection_cpu": {
        "problemId": "P-20250401-003",
        "problemTitle": "CPU saturation on fraud-detection service",
        "state": "OPEN",
        "severity": "RESOURCE_CONTENTION",
        "impactLevel": "INFRASTRUCTURE",
        "affectedEntities": [
            {"entityId": "SERVICE-FRAUD001", "name": "fraud-detection"},
        ],
        "rootCauseEntity": {
            "entityId": "PROCESS-FRAUD001",
            "name": "fraud-detection-process"
        },
        "events": [
            {
                "eventType": "CPU_SATURATION_EVENT",
                "description": "CPU usage reached 95% — above 80% threshold"
            },
            {
                "eventType": "HIGH_GC_ACTIVITY",
                "description": "JVM garbage collection taking 40% of CPU time"
            }
        ],
        "tags": ["fraud-detection", "ml-services", "production"],
        "impactedUsers": 0,
        "startTime": "2025-04-01T04:01:00Z"
    }
}


# ─────────────────────────────────────────
# FUNCTION 1: extract_dynatrace_fields
# Normalises Dynatrace problem payload
# Maps to consistent flat structure
# ─────────────────────────────────────────
def extract_dynatrace_fields(problem):
    """
    Extracts and normalises key fields from
    a Dynatrace problem notification.
    Maps Dynatrace severity to P1/P2/P3.
    Returns clean flat dictionary.
    """
    # Extract affected entity names as list
    affected = [
        e.get("name", "unknown")
        for e in problem.get("affectedEntities", [])
    ]

    # Extract event descriptions as list
    events = [
        f"{e.get('eventType','')}: {e.get('description','')}"
        for e in problem.get("events", [])
    ]

    # Map Dynatrace severity to P1/P2/P3
    dt_severity = problem.get("severity", "CUSTOM_ALERT")
    priority = SEVERITY_MAP.get(dt_severity, "P3")

    return {
        "problem_id":      problem.get("problemId", "unknown"),
        "title":           problem.get("problemTitle", "unknown"),
        "severity":        dt_severity,
        "priority":        priority,
        "state":           problem.get("state", "unknown"),
        "impact_level":    problem.get("impactLevel", "unknown"),
        "affected":        ", ".join(affected),
        "root_cause":      problem.get("rootCauseEntity", {}).get("name", "unknown"),
        "events":          " | ".join(events),
        "tags":            ", ".join(problem.get("tags", [])),
        "impacted_users":  problem.get("impactedUsers", 0),
        "start_time":      problem.get("startTime", "unknown"),
    }


# ─────────────────────────────────────────
# FUNCTION 2: build_dynatrace_prompt
# Builds AI enrichment prompt using
# Dynatrace-specific context and terminology
# ─────────────────────────────────────────
def build_dynatrace_prompt(fields):
    """
    Builds enrichment prompt for Dynatrace problem.
    Includes Dynatrace-specific context so LLM
    understands Davis AI concepts.
    """
    return f"""
You are a senior SRE engineer at a fintech company.
You are analyzing a Dynatrace problem notification.

Dynatrace uses 'Problems' which group related symptoms
with a root cause identified by Davis AI.
Your job is to enrich this with actionable guidance.

Return ONLY valid JSON:
{{
  "problem_id": "{fields['problem_id']}",
  "priority": "{fields['priority']}",
  "summary": "<one sentence plain English summary>",
  "root_cause_analysis": "<2 sentence analysis of what caused this>",
  "business_impact": "<how this affects end users or business>",
  "immediate_actions": [
    "<action 1 — most urgent>",
    "<action 2>",
    "<action 3>"
  ],
  "dynatrace_actions": [
    "<what to check in Dynatrace UI>",
    "<which Dynatrace view to open>"
  ],
  "kubectl_commands": [
    "<relevant kubectl command 1>",
    "<relevant kubectl command 2>"
  ],
  "escalate": <true or false>,
  "escalate_reason": "<why escalation is needed if true>"
}}

Problem Details:
- Problem ID    : {fields['problem_id']}
- Title         : {fields['title']}
- Severity      : {fields['severity']} → {fields['priority']}
- Impact Level  : {fields['impact_level']}
- Affected      : {fields['affected']}
- Root Cause    : {fields['root_cause']}
- Events        : {fields['events']}
- Tags          : {fields['tags']}
- Impacted Users: {fields['impacted_users']}
- Started At    : {fields['start_time']}

Rules:
- Return JSON only. No text before or after.
- escalate must be true if priority is P1
- immediate_actions must be ordered by urgency
- kubectl_commands must be real and relevant to the problem
- business_impact must mention impacted users if > 0
"""


# ─────────────────────────────────────────
# FUNCTION 3: call_llm
# Standard Groq call — same pattern
# ─────────────────────────────────────────
def call_llm(prompt):
    """Calls Groq LLaMA. Returns parsed JSON or None."""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior SRE engineer. "
                        "Always return valid JSON only. "
                        "No markdown. No explanation outside JSON."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None


# ─────────────────────────────────────────
# FUNCTION 4: format_dynatrace_output
# Prints formatted problem analysis
# Shows Dynatrace-specific guidance
# ─────────────────────────────────────────
def format_dynatrace_output(result, fields):
    """
    Prints formatted Dynatrace problem analysis.
    Shows both Dynatrace UI actions and kubectl.
    """
    priority = result.get("priority", "P3")
    emojis = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}
    emoji = emojis.get(priority, "⚪")

    print(f"\n{'='*60}")
    print(f"{emoji}  {priority} — {fields['title']}")
    print(f"    Problem ID: {fields['problem_id']}")
    print(f"    Severity  : {fields['severity']}")
    print(f"    Users     : {fields['impacted_users']} affected")
    print(f"{'='*60}")
    print(f"\nSummary:")
    print(f"  {result.get('summary', 'unknown')}")
    print(f"\nRoot Cause Analysis:")
    print(f"  {result.get('root_cause_analysis', 'unknown')}")
    print(f"\nBusiness Impact:")
    print(f"  {result.get('business_impact', 'unknown')}")

    actions = result.get("immediate_actions", [])
    if actions:
        print(f"\nImmediate Actions:")
        for i, a in enumerate(actions, 1):
            print(f"  {i}. {a}")

    dt_actions = result.get("dynatrace_actions", [])
    if dt_actions:
        print(f"\nDynatrace UI Actions:")
        for a in dt_actions:
            print(f"  📊 {a}")

    kubectl = result.get("kubectl_commands", [])
    if kubectl:
        print(f"\nKubectl Commands:")
        for cmd in kubectl:
            print(f"  $ {cmd}")

    if result.get("escalate"):
        print(f"\n⚠️  ESCALATE: {result.get('escalate_reason', '')}")


# ─────────────────────────────────────────
# FUNCTION 5: handle_dynatrace_problem
# Main orchestrator
# ─────────────────────────────────────────
def handle_dynatrace_problem(problem, problem_name="unknown"):
    """
    Full Dynatrace problem handling pipeline.
    Returns enriched result dict or None.
    """
    print(f"\nProcessing: {problem_name}")

    # Step 1: Extract and normalise fields
    fields = extract_dynatrace_fields(problem)
    print(f"Priority: {fields['priority']} | "
          f"Users affected: {fields['impacted_users']}")

    # Step 2: Build enrichment prompt
    prompt = build_dynatrace_prompt(fields)

    # Step 3: AI enrichment
    result = call_llm(prompt)

    if result:
        # Step 4: Print formatted output
        format_dynatrace_output(result, fields)
        return result
    else:
        print(f"Enrichment failed for {problem_name}")
        return None


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("Dynatrace Alert Handler — Starting")
    print("Powered by Groq + LLaMA 3.3\n")

    results = {}

    for problem_name, problem_data in DYNATRACE_PROBLEMS.items():
        result = handle_dynatrace_problem(
            problem_data, problem_name
        )
        if result:
            results[problem_name] = result

    print(f"\n{'='*60}")
    print(f"Done. Processed {len(results)}/3 problems.")

    print(f"\nPROBLEM SUMMARY:")
    for name, result in results.items():
        priority = result.get("priority", "unknown")
        escalate = "⚠️ Escalate" if result.get("escalate") else "✅ Monitor"
        users = DYNATRACE_PROBLEMS[name].get("impactedUsers", 0)
        print(f"  {name:30} → {priority} | {escalate} | {users} users")