"""
Kubernetes Log Analyzer
=======================
Analyzes raw Kubernetes pod logs using Gemini AI.
Returns structured JSON diagnosis with error type,
root cause, immediate action, fix, and severity.

Tools used: Gemini API, Python
Part of: GenAI for DevOps & SRE — Phase 1
Author: Bhagyashree
Day: 3
"""

from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ─────────────────────────────────────────
# SAMPLE LOGS — 3 real Kubernetes error types
# These are logs you would actually see at JPMC
# ─────────────────────────────────────────

LOGS = {
    "crash_loop": """
    Warning  BackOff    2m    kubelet  Back-off restarting failed container
    Error: failed to start container "payment-api"
    Exit Code: 1
    Reason: Error
    Message: failed to create containerd task:
    OCI runtime create failed: container_linux.go:380
    starting container process caused: exec: "python":
    executable file not found in $PATH
    Pod: payment-api-7d9f8b-xk2pl
    Namespace: production
    Restarts: 12
    Node: ip-10-0-1-45
    """,

    "oom_killed": """
    Warning  OOMKilling  5m  kernel  Out of memory: Kill process 12847
    (java) score 1847 or sacrifice child
    Killed process 12847 (java) total-vm:4823456kB
    anon-rss:2097152kB, file-rss:0kB, shmem-rss:0kB
    oom_reaper: reaped process 12847
    Container: order-service
    Pod: order-service-6c8d9f-mn4kl
    Namespace: production
    Memory Limit: 512Mi
    Memory Usage at death: 512Mi
    Restarts: 3
    """,

    "image_pull": """
    Warning  Failed     3m    kubelet  Failed to pull image
    "registry.jpmc.internal/payments/api:v2.3.1-hotfix":
    rpc error: code = Unknown
    desc = failed to pull and unpack image:
    failed to resolve reference "registry.jpmc.internal/payments/api:v2.3.1-hotfix":
    unexpected status code 401 Unauthorized
    Warning  Failed     3m    kubelet  Error: ErrImagePull
    Warning  BackOff    2m    kubelet  Back-off pulling image
    Pod: payments-api-new-5f7b9c-pq8rs
    Namespace: staging
    """,
}


# ─────────────────────────────────────────
# FUNCTION 1: chunk_log
# Splits large logs into smaller pieces
# so they fit within the LLM context window
# In production logs can be 100,000+ lines
# ─────────────────────────────────────────
def chunk_log(log_text, max_lines=100):
    """
    Splits a log into chunks of max_lines each.
    Returns a list of chunks.
    For today's logs this returns just one chunk
    since they are small — but the logic is ready
    for production use.
    """
    lines = log_text.strip().split('\n')

    # If log fits in one chunk — return as single item list
    if len(lines) <= max_lines:
        return [log_text]

    # Otherwise split into chunks
    chunks = []
    for i in range(0, len(lines), max_lines):
        chunk = '\n'.join(lines[i:i + max_lines])
        chunks.append(chunk)

    return chunks


# ─────────────────────────────────────────
# FUNCTION 2: build_prompt
# Builds the engineered prompt for each log
# Uses few-shot technique from Day 2
# ─────────────────────────────────────────
def build_prompt(log_chunk):
    """
    Builds a structured prompt with examples
    (few-shot) so Gemini always returns the
    exact JSON format we need.
    """
    return f"""
You are a senior SRE engineer at a fintech company.
Analyze the Kubernetes log below and return ONLY a valid JSON object.

Here are two examples of correct output format:

Example 1:

Log: "OOMKilled: container exceeded memory limit, restarts: 5"
Output: {{
  "error_type": "OOMKilled",
  "affected_component": "unknown",
  "root_cause": "Container exceeded its memory limit and was killed by the kernel",
  "immediate_action": "kubectl describe pod <pod-name> -n <namespace>",
  "fix": "Increase memory limit in deployment spec or optimize application memory usage",
  "severity": "P1",
  "confidence": "High"
}}

Example 2:
Log: "ImagePullBackOff: unable to pull image from registry"
Output: {{
  "error_type": "ImagePullBackOff",
  "affected_component": "unknown",
  "root_cause": "Kubernetes cannot pull the container image from the registry",
  "immediate_action": "kubectl describe pod <pod-name> | grep -A5 Events",
  "fix": "Check image name spelling, registry credentials, and network access to registry",
  "severity": "P2",
  "confidence": "High"
}}

Now analyze this log. Return JSON only. No explanation outside the JSON.
Use "unknown" for any field you cannot determine from the log.
Severity must be P1 (critical), P2 (high) or P3 (medium).

Log to analyze:
{log_chunk}
"""


# ─────────────────────────────────────────
# FUNCTION 3: analyze_log
# Main function — sends log to Gemini
# parses response, returns structured dict
# ─────────────────────────────────────────
def analyze_log(log_text, log_name):
    """
    Takes a raw log string, chunks it,
    sends to Gemini, parses JSON response.
    Returns structured diagnosis dictionary.
    """
    print(f"\n{'='*60}")
    print(f"Analyzing: {log_name}")
    print(f"{'='*60}")

    # Step 1: chunk the log
    chunks = chunk_log(log_text)
    print(f"Log split into {len(chunks)} chunk(s)")

    # Step 2: analyze first chunk
    # In production you'd analyze all chunks
    # and merge results — we'll build that later
    prompt = build_prompt(chunks[0])

    # Step 3: call Gemini
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a senior SRE engineer. "
                "Always return valid JSON only. "
                "No markdown formatting. No explanation outside JSON."
            ),
            temperature=0,  # always 0 for SRE tools
        ),
        contents=prompt
    )

    # Step 4: clean and parse JSON
    try:
        raw = response.text.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        # Step 5: print formatted diagnosis
        print(f"\n🔍 DIAGNOSIS:")
        print(f"   Error Type  : {result.get('error_type', 'unknown')}")
        print(f"   Component   : {result.get('affected_component', 'unknown')}")
        print(f"   Severity    : {result.get('severity', 'unknown')}")
        print(f"   Confidence  : {result.get('confidence', 'unknown')}")
        print(f"\n📋 ROOT CAUSE:")
        print(f"   {result.get('root_cause', 'unknown')}")
        print(f"\n⚡ IMMEDIATE ACTION:")
        print(f"   {result.get('immediate_action', 'unknown')}")
        print(f"\n🔧 FIX:")
        print(f"   {result.get('fix', 'unknown')}")

        # Step 6: format Slack message preview
        severity = result.get('severity', 'P3')
        emoji = "🔴" if severity == "P1" else "🟡" if severity == "P2" else "🟢"

        slack_preview = f"""
{emoji} *{severity} — {result.get('error_type', 'Unknown Error')}*
*Component:* {result.get('affected_component', 'unknown')}
*Root Cause:* {result.get('root_cause', 'unknown')}
*Action:* `{result.get('immediate_action', 'unknown')}`
*Fix:* {result.get('fix', 'unknown')}
        """
        print(f"\n💬 SLACK MESSAGE PREVIEW:")
        print(slack_preview)

        return result

    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing failed: {e}")
        print(f"Raw response: {response.text}")
        return None


# ─────────────────────────────────────────
# MAIN — run analyzer on all 3 log types
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Kubernetes Log Analyzer — Starting")
    print("Powered by Gemini 2.5 Flash\n")

    results = {}

    for log_name, log_text in LOGS.items():
        result = analyze_log(log_text, log_name)
        if result:
            results[log_name] = result

    print(f"\n{'='*60}")
    print(f"✅ Analysis complete. Processed {len(results)}/3 logs successfully.")
    print(f"{'='*60}")