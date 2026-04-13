"""
Prometheus + Grafana AI Integration
=====================================
Tool 1 — PromQL Assistant:
  Takes plain English description of what
  you want to monitor and returns valid
  PromQL query with explanation.

Tool 2 — Dashboard Narrator:
  Takes Grafana dashboard metric snapshot
  and generates plain English executive
  summary with health status and actions.

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 11
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─────────────────────────────────────────
# SAMPLE DATA
# ─────────────────────────────────────────

# Plain English monitoring questions
# Your PromQL assistant will answer these
PROMQL_QUESTIONS = [
    "Show me CPU usage above 80% for all pods in production namespace",
    "What is the HTTP error rate for payment-api in the last 5 minutes",
    "Show memory usage as a percentage for all nodes",
    "Alert me when a pod has restarted more than 5 times in last hour",
    "Show me request latency above 500ms for auth-service",
]

# Simulated Grafana dashboard snapshots
# In production these come from Grafana HTTP API
# Structure mirrors real Grafana panel data
DASHBOARD_SNAPSHOTS = {

    "payment_api_dashboard": {
        "dashboard_name": "Payment API — Production",
        "captured_at": "2025-04-01 03:22:00",
        "service": "payment-api",
        "environment": "production",
        "panels": {
            "cpu_usage": {
                "value": 94.2,
                "unit": "%",
                "threshold": 80.0,
                "status": "critical",
                "trend": "increasing"
            },
            "memory_usage": {
                "value": 67.5,
                "unit": "%",
                "threshold": 85.0,
                "status": "healthy",
                "trend": "stable"
            },
            "error_rate": {
                "value": 3.4,
                "unit": "%",
                "threshold": 1.0,
                "status": "critical",
                "trend": "increasing"
            },
            "request_rate": {
                "value": 1250,
                "unit": "req/s",
                "threshold": 1000,
                "status": "warning",
                "trend": "spike"
            },
            "p99_latency": {
                "value": 850,
                "unit": "ms",
                "threshold": 500,
                "status": "critical",
                "trend": "increasing"
            },
            "pod_count": {
                "value": 8,
                "unit": "pods",
                "threshold": 10,
                "status": "healthy",
                "trend": "stable"
            }
        }
    },

    "infrastructure_dashboard": {
        "dashboard_name": "Infrastructure — All Nodes",
        "captured_at": "2025-04-01 04:00:00",
        "service": "infrastructure",
        "environment": "production",
        "panels": {
            "node_cpu_avg": {
                "value": 45.0,
                "unit": "%",
                "threshold": 80.0,
                "status": "healthy",
                "trend": "stable"
            },
            "node_memory_avg": {
                "value": 72.0,
                "unit": "%",
                "threshold": 85.0,
                "status": "healthy",
                "trend": "stable"
            },
            "disk_usage": {
                "value": 78.0,
                "unit": "%",
                "threshold": 85.0,
                "status": "warning",
                "trend": "increasing"
            },
            "pod_restart_count": {
                "value": 12,
                "unit": "restarts",
                "threshold": 5,
                "status": "critical",
                "trend": "increasing"
            },
            "network_errors": {
                "value": 0.02,
                "unit": "%",
                "threshold": 0.1,
                "status": "healthy",
                "trend": "stable"
            }
        }
    }
}


# ═══════════════════════════════════════
# TOOL 1: PromQL ASSISTANT
# ═══════════════════════════════════════

def build_promql_prompt(question):
    """
    Builds prompt for PromQL query generation.
    Includes common Prometheus metric names
    so LLM generates accurate queries.
    """
    return f"""
You are a senior SRE engineer and Prometheus expert.
Generate a PromQL query for the request below.

Common Prometheus metric names to use:
- CPU: rate(container_cpu_usage_seconds_total[5m])
- Memory: container_memory_usage_bytes
- Pod restarts: kube_pod_container_status_restarts_total
- HTTP requests: rate(http_requests_total[5m])
- HTTP errors: rate(http_requests_total{{status=~"5.."}}[5m])
- Request latency: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
- Node memory: node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
- Node CPU: 1 - avg(rate(node_cpu_seconds_total{{mode="idle"}}[5m]))

Return ONLY valid JSON:
{{
  "question": "<original question>",
  "promql_query": "<the PromQL query>",
  "explanation": "<plain English explanation of what the query does>",
  "alert_rule": "<how to use this as a Prometheus alert rule>",
  "grafana_tip": "<how to visualise this in Grafana>"
}}

Rules:
- Return JSON only. No text before or after.
- promql_query must be valid PromQL syntax
- Use realistic label selectors like namespace, service, pod
- explanation must be understandable by a non-expert

Request: {question}
"""


def call_llm(prompt, system="You are a senior SRE engineer. Always return valid JSON only. No markdown. No explanation outside JSON."):
    """Calls Groq LLaMA. Returns parsed JSON or None."""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system},
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


def generate_promql(question):
    """
    Generates PromQL query from plain English.
    Returns structured result with query and explanation.
    """
    prompt = build_promql_prompt(question)
    result = call_llm(prompt)

    if result:
        print(f"\n{'='*60}")
        print(f"QUESTION: {question}")
        print(f"{'='*60}")
        print(f"PromQL Query:")
        print(f"  {result.get('promql_query', 'unknown')}")
        print(f"\nExplanation:")
        print(f"  {result.get('explanation', 'unknown')}")
        print(f"\nAlert Rule:")
        print(f"  {result.get('alert_rule', 'unknown')}")
        print(f"\nGrafana Tip:")
        print(f"  {result.get('grafana_tip', 'unknown')}")
        return result
    else:
        print(f"Failed to generate PromQL for: {question}")
        return None


# ═══════════════════════════════════════
# TOOL 2: DASHBOARD NARRATOR
# ═══════════════════════════════════════

def calculate_panel_summary(panels):
    """
    Pre-processes panel data before sending to LLM.
    Calculates how many panels are critical, warning, healthy.
    Reduces token usage by summarising before sending.
    """
    summary = {
        "critical": [],
        "warning": [],
        "healthy": []
    }

    for panel_name, panel_data in panels.items():
        status = panel_data.get("status", "unknown")
        value = panel_data.get("value", 0)
        unit = panel_data.get("unit", "")
        threshold = panel_data.get("threshold", 0)
        trend = panel_data.get("trend", "stable")

        # Format: "cpu_usage: 94.2% (threshold: 80%, trend: increasing)"
        entry = (
            f"{panel_name}: {value}{unit} "
            f"(threshold: {threshold}{unit}, trend: {trend})"
        )
        summary[status].append(entry)

    return summary


def build_narrator_prompt(snapshot):
    """
    Builds prompt for dashboard narration.
    Pre-processes panels into critical/warning/healthy
    groups before sending — cleaner for LLM.
    """
    panel_summary = calculate_panel_summary(
        snapshot.get("panels", {})
    )

    return f"""
You are a senior SRE engineer writing an executive summary
for a Grafana dashboard. Write for both technical and
non-technical stakeholders.

Dashboard: {snapshot.get('dashboard_name')}
Service  : {snapshot.get('service')}
Captured : {snapshot.get('captured_at')}
Environment: {snapshot.get('environment')}

Panel Status Summary:
CRITICAL panels: {panel_summary['critical']}
WARNING panels : {panel_summary['warning']}
HEALTHY panels : {panel_summary['healthy']}

Return ONLY valid JSON:
{{
  "overall_status": "<Healthy, Degraded, Critical or Down>",
  "headline": "<one sentence summary for a manager>",
  "narrative": "<2-3 sentences describing what is happening>",
  "critical_findings": ["<finding 1>", "<finding 2>"],
  "positive_findings": ["<what is working well>"],
  "recommended_actions": ["<action 1>", "<action 2>", "<action 3>"],
  "escalation_needed": <true or false>
}}

Rules:
- Return JSON only. No text before or after.
- headline must be understandable by a non-technical manager
- narrative must connect the metrics to business impact
- recommended_actions must be specific and actionable
- escalation_needed true if overall_status is Critical or Down
"""


def narrate_dashboard(snapshot, dashboard_name):
    """
    Generates plain English narrative for dashboard.
    Combines pre-processing with LLM narration.
    """
    print(f"\n{'='*60}")
    print(f"NARRATING: {snapshot.get('dashboard_name')}")
    print(f"{'='*60}")

    prompt = build_narrator_prompt(snapshot)
    result = call_llm(prompt)

    if result:
        status = result.get('overall_status', 'Unknown')
        status_emojis = {
            "Healthy": "🟢",
            "Degraded": "🟡",
            "Critical": "🔴",
            "Down": "💀"
        }
        emoji = status_emojis.get(status, "⚪")

        print(f"\n{emoji}  Overall Status: {status}")
        print(f"\nHeadline:")
        print(f"  {result.get('headline', 'unknown')}")
        print(f"\nNarrative:")
        print(f"  {result.get('narrative', 'unknown')}")

        critical = result.get('critical_findings', [])
        if critical:
            print(f"\nCritical Findings:")
            for f in critical:
                print(f"  🔴 {f}")

        positive = result.get('positive_findings', [])
        if positive:
            print(f"\nPositive Findings:")
            for f in positive:
                print(f"  🟢 {f}")

        actions = result.get('recommended_actions', [])
        if actions:
            print(f"\nRecommended Actions:")
            for i, a in enumerate(actions, 1):
                print(f"  {i}. {a}")

        if result.get('escalation_needed'):
            print(f"\n⚠️  ESCALATION REQUIRED")

        return result
    else:
        print(f"Narration failed for {dashboard_name}")
        return None


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":

    # ── TOOL 1: PromQL Assistant ──
    print("\n" + "="*60)
    print("TOOL 1: PromQL ASSISTANT")
    print("="*60)
    print("Generating PromQL queries from plain English...\n")

    promql_results = {}
    # Run first 3 questions to stay within rate limits
    for question in PROMQL_QUESTIONS[:3]:
        result = generate_promql(question)
        if result:
            promql_results[question[:30]] = result

    print(f"\nGenerated {len(promql_results)}/3 PromQL queries")

    # ── TOOL 2: Dashboard Narrator ──
    print("\n" + "="*60)
    print("TOOL 2: DASHBOARD NARRATOR")
    print("="*60)
    print("Generating dashboard narratives...\n")

    narrator_results = {}
    for dashboard_name, snapshot in DASHBOARD_SNAPSHOTS.items():
        result = narrate_dashboard(snapshot, dashboard_name)
        if result:
            narrator_results[dashboard_name] = result

    print(f"\n{'='*60}")
    print(f"Done. PromQL: {len(promql_results)}/3 | Dashboards: {len(narrator_results)}/2")
    print(f"{'='*60}")

    # Final summary
    print("\nDASHBOARD STATUS SUMMARY:")
    for name, result in narrator_results.items():
        status = result.get('overall_status', 'Unknown')
        escalate = "⚠️ Escalate" if result.get('escalation_needed') else "✅ Monitor"
        print(f"  {name:35} → {status:10} | {escalate}")