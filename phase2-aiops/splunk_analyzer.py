"""
Splunk Log Analyzer
===================
Analyzes exported Splunk logs using AI.
Returns error counts, top errors, affected
services, patterns and recommended actions.

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 9
"""

import json
import time
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Groq client — free, no rate limit issues
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────
# SAMPLE SPLUNK LOGS
# 3 real scenarios from fintech environment
# Similar to what you see at JPMC
# ─────────────────────────────────────────
SPLUNK_LOGS = {

    "payment_service_errors": """
2025-04-01 03:15:22 ERROR PaymentService - Transaction failed: Connection timeout to DB
2025-04-01 03:15:23 ERROR PaymentService - Transaction failed: Connection timeout to DB
2025-04-01 03:15:25 WARN  PaymentService - Retry attempt 1 of 3 for transaction TXN-4521
2025-04-01 03:15:28 ERROR PaymentService - Transaction failed: Connection timeout to DB
2025-04-01 03:15:30 ERROR DatabasePool - Max connections reached: 100/100
2025-04-01 03:15:31 ERROR PaymentService - Transaction failed: Connection timeout to DB
2025-04-01 03:15:33 WARN  PaymentService - Retry attempt 2 of 3 for transaction TXN-4521
2025-04-01 03:15:35 ERROR PaymentService - Circuit breaker OPEN for DB connection
2025-04-01 03:15:36 FATAL PaymentService - Service degraded: Unable to process payments
2025-04-01 03:15:37 ERROR AuthService - Token validation failed: DB unreachable
2025-04-01 03:15:38 ERROR AuthService - Token validation failed: DB unreachable
2025-04-01 03:15:40 WARN  LoadBalancer - Removing payment-api-pod-3 from rotation
2025-04-01 03:15:42 ERROR PaymentService - Transaction failed: Service in degraded state
""",

    "kubernetes_events": """
2025-04-01 04:22:10 WARN  Kubelet - Pod order-service-7d9f is restarting frequently
2025-04-01 04:22:11 ERROR Kubelet - Container order-service failed liveness probe
2025-04-01 04:22:12 INFO  Scheduler - Evicting pod order-service-7d9f from node ip-10-0-1-45
2025-04-01 04:22:13 WARN  Kubelet - Node ip-10-0-1-45 memory pressure detected
2025-04-01 04:22:14 ERROR Kubelet - Container order-service OOMKilled
2025-04-01 04:22:15 INFO  Scheduler - Scheduling order-service-7d9f to node ip-10-0-1-46
2025-04-01 04:22:20 ERROR Kubelet - Container order-service failed liveness probe
2025-04-01 04:22:21 WARN  HPA - order-service CPU above 85% scaling up
2025-04-01 04:22:25 ERROR Kubelet - Container order-service failed liveness probe
2025-04-01 04:22:30 ERROR Kubelet - Container order-service CrashLoopBackOff
""",

    "api_gateway_logs": """
2025-04-01 05:10:01 INFO  APIGateway - GET /api/v1/accounts 200 45ms
2025-04-01 05:10:02 INFO  APIGateway - POST /api/v1/payments 200 120ms
2025-04-01 05:10:03 ERROR APIGateway - POST /api/v1/payments 503 timeout upstream
2025-04-01 05:10:04 ERROR APIGateway - POST /api/v1/payments 503 timeout upstream
2025-04-01 05:10:05 ERROR APIGateway - POST /api/v1/payments 503 timeout upstream
2025-04-01 05:10:06 WARN  APIGateway - Circuit breaker triggered for payment-service
2025-04-01 05:10:07 ERROR APIGateway - GET /api/v1/auth/validate 500 internal error
2025-04-01 05:10:08 ERROR APIGateway - GET /api/v1/auth/validate 500 internal error
2025-04-01 05:10:09 INFO  APIGateway - GET /api/v1/accounts 200 52ms
2025-04-01 05:10:10 ERROR APIGateway - POST /api/v1/payments 503 timeout upstream
2025-04-01 05:10:11 WARN  RateLimiter - Client 192.168.1.45 exceeded rate limit
2025-04-01 05:10:12 ERROR APIGateway - POST /api/v1/payments 503 timeout upstream
"""
}


# ─────────────────────────────────────────
# FUNCTION 1: chunk_log
# Splits large logs into manageable pieces
# that fit within the LLM context window
# ─────────────────────────────────────────
def chunk_log(log_text, max_lines=50):
    """
    Splits large logs into chunks.
    Returns list of chunks.
    For small logs returns single item list.
    """
    lines = log_text.strip().split('\n')
    if len(lines) <= max_lines:
        return [log_text]
    chunks = []
    for i in range(0, len(lines), max_lines):
        chunk = '\n'.join(lines[i:i + max_lines])
        chunks.append(chunk)
    return chunks


# ─────────────────────────────────────────
# FUNCTION 2: build_splunk_prompt
# Builds engineered prompt for Splunk
# log analysis with exact JSON structure
# ─────────────────────────────────────────
def build_splunk_prompt(log_chunk, time_range="last 1 hour"):
    """
    Builds structured prompt for Splunk log analysis.
    Uses few-shot technique for consistent JSON output.
    """
    return f"""
You are a senior SRE engineer analyzing Splunk logs
from a fintech company. Time range: {time_range}

Analyze the logs below and return ONLY valid JSON:
{{
  "error_count": <total number of ERROR level entries>,
  "warning_count": <total number of WARN level entries>,
  "fatal_count": <total number of FATAL level entries>,
  "top_errors": [
    "<most frequent or impactful error 1>",
    "<error 2>",
    "<error 3>"
  ],
  "affected_services": ["<service 1>", "<service 2>"],
  "time_of_first_error": "<timestamp of first ERROR line>",
  "pattern": "<description of the error pattern or trend>",
  "root_cause": "<probable root cause in one sentence>",
  "severity": "<P1, P2 or P3>",
  "recommended_action": "<single most important action to take first>"
}}

Rules:
- Return JSON only. No text before or after.
- top_errors: pick the 3 most frequent or highest impact
- severity P1 if FATAL present or critical service down
- severity P2 if repeated errors but service partially up
- severity P3 if warnings only or low impact errors
- If no errors found: set error_count to 0, severity to P3

Splunk logs to analyze:
{log_chunk}
"""


# ─────────────────────────────────────────
# FUNCTION 3: call_llm
# Calls Groq API with LLaMA model
# Same interface as call_gemini from Day 8
# ─────────────────────────────────────────
def call_llm(prompt):
    """
    Sends prompt to Groq LLaMA model.
    Returns parsed JSON dict or None on failure.
    Groq is free with no availability issues.
    """
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
                {
                    "role": "user",
                    "content": prompt
                }
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
# FUNCTION 4: format_splunk_output
# Prints formatted analysis to terminal
# Colour coded by severity
# ─────────────────────────────────────────
def format_splunk_output(result, log_name):
    """
    Prints formatted Splunk analysis.
    Shows counts, pattern, root cause, actions.
    """
    severity = result.get('severity', 'P3')
    emojis = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}
    emoji = emojis.get(severity, "⚪")

    print(f"\n{'='*60}")
    print(f"{emoji}  SPLUNK ANALYSIS: {log_name.upper()}")
    print(f"{'='*60}")
    print(f"Severity         : {severity}")
    print(f"Errors           : {result.get('error_count', 0)}")
    print(f"Warnings         : {result.get('warning_count', 0)}")
    print(f"Fatals           : {result.get('fatal_count', 0)}")
    print(f"First Error      : {result.get('time_of_first_error', 'unknown')}")

    services = result.get('affected_services', [])
    if services:
        print(f"Affected Services: {', '.join(services)}")

    print(f"\nPattern    : {result.get('pattern', 'unknown')}")
    print(f"Root Cause : {result.get('root_cause', 'unknown')}")

    errors = result.get('top_errors', [])
    if errors:
        print(f"\nTop Errors:")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")

    print(f"\nAction : {result.get('recommended_action', 'unknown')}")


# ─────────────────────────────────────────
# FUNCTION 5: analyze_splunk_logs
# Main orchestrator — full pipeline
# chunk → prompt → LLM → format output
# ─────────────────────────────────────────
def analyze_splunk_logs(log_text, log_name="unknown"):
    """
    Full Splunk analysis pipeline.
    Returns enriched analysis dict or None.
    """
    print(f"\nAnalyzing: {log_name}")

    # Step 1: Chunk the log
    chunks = chunk_log(log_text)
    print(f"Log split into {len(chunks)} chunk(s)")

    # Step 2: Build prompt for first chunk
    prompt = build_splunk_prompt(chunks[0])

    # Step 3: Call LLM
    result = call_llm(prompt)

    if result:
        # Step 4: Print formatted output
        format_splunk_output(result, log_name)
        return result
    else:
        print(f"Analysis failed for {log_name}")
        return None


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("Splunk Log Analyzer — Starting")
    print("Powered by Groq + LLaMA 3.3\n")

    results = {}

    for log_name, log_text in SPLUNK_LOGS.items():
        result = analyze_splunk_logs(log_text, log_name)
        if result:
            results[log_name] = result
        # Small delay between calls — good practice
        time.sleep(3)

    print(f"\n{'='*60}")
    print(f"Done. Analyzed {len(results)}/3 log sets.")
    print(f"\nSEVERITY SUMMARY:")
    for name, result in results.items():
        sev = result.get('severity', 'unknown')
        errors = result.get('error_count', 0)
        print(f"  {name:30} → {sev} ({errors} errors)")