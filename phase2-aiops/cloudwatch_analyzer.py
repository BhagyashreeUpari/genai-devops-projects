"""
AWS CloudWatch Log Analyzer
============================
Analyzes CloudWatch logs from Lambda, ECS,
API Gateway and RDS using AI.

Works with simulated logs today.
In production: connect to boto3 CloudWatch
Logs client to fetch real logs.

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 13
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─────────────────────────────────────────
# CLOUDWATCH LOG GROUPS
# Each dict represents one log group
# with its source type and sample logs
# ─────────────────────────────────────────
CLOUDWATCH_LOGS = {

    "lambda_payment_processor": {
        "log_group": "/aws/lambda/payment-processor",
        "service_type": "Lambda",
        "region": "ap-south-1",
        "logs": """
2025-04-01T03:15:20.123Z START RequestId: abc-123-def Duration: 0ms
2025-04-01T03:15:20.456Z INFO  RequestId: abc-123-def Processing payment TXN-4521
2025-04-01T03:15:22.789Z ERROR RequestId: abc-123-def Connection timeout: payments-db.internal:5432
2025-04-01T03:15:22.801Z ERROR RequestId: abc-123-def Retry attempt 1: Connection refused
2025-04-01T03:15:23.901Z ERROR RequestId: abc-123-def Retry attempt 2: Connection refused
2025-04-01T03:15:25.001Z ERROR RequestId: abc-123-def Max retries exceeded for payments-db
2025-04-01T03:15:25.012Z END   RequestId: abc-123-def
2025-04-01T03:15:25.013Z REPORT RequestId: abc-123-def Duration: 4890ms Billed: 4900ms Memory: 512MB Max: 498MB
2025-04-01T03:15:26.100Z START RequestId: xyz-456-uvw Duration: 0ms
2025-04-01T03:15:26.150Z INFO  RequestId: xyz-456-uvw Processing payment TXN-4522
2025-04-01T03:15:56.200Z ERROR RequestId: xyz-456-uvw Task timed out after 30.00 seconds
2025-04-01T03:15:56.201Z REPORT RequestId: xyz-456-uvw Duration: 30000ms Billed: 30000ms Memory: 512MB Max: 510MB
"""
    },

    "ecs_fraud_detection": {
        "log_group": "/ecs/production/fraud-detection",
        "service_type": "ECS",
        "region": "ap-south-1",
        "logs": """
2025-04-01T04:00:01.000Z INFO  FraudDetectionService - Starting model inference
2025-04-01T04:00:01.500Z INFO  FraudDetectionService - Loading ML model v2.3
2025-04-01T04:00:05.200Z WARN  FraudDetectionService - Model inference latency: 3700ms (threshold: 2000ms)
2025-04-01T04:00:08.400Z ERROR FraudDetectionService - OutOfMemoryError: Java heap space
2025-04-01T04:00:08.401Z ERROR FraudDetectionService - at com.jpmc.fraud.ModelInference.predict(ModelInference.java:245)
2025-04-01T04:00:08.402Z ERROR FraudDetectionService - GC overhead limit exceeded
2025-04-01T04:00:09.000Z WARN  ECS - Container fraud-detection health check failed
2025-04-01T04:00:10.000Z INFO  ECS - Stopping container fraud-detection (exit code: 137)
2025-04-01T04:00:11.000Z INFO  ECS - Starting replacement container fraud-detection
2025-04-01T04:00:15.000Z ERROR FraudDetectionService - OutOfMemoryError: Java heap space
2025-04-01T04:00:15.001Z INFO  ECS - Stopping container fraud-detection (exit code: 137)
"""
    },

    "api_gateway_errors": {
        "log_group": "API-Gateway-Execution-Logs/payments-api/prod",
        "service_type": "API Gateway",
        "region": "ap-south-1",
        "logs": """
2025-04-01T05:10:01.000Z INFO  (b1c2d3) payments-api Method: POST Resource: /v1/payments
2025-04-01T05:10:01.100Z INFO  (b1c2d3) Endpoint: https://payment-processor.internal/process
2025-04-01T05:10:31.200Z ERROR (b1c2d3) Execution failed: Integration Timeout 29000ms
2025-04-01T05:10:31.201Z ERROR (b1c2d3) Method completed with status: 504
2025-04-01T05:10:32.000Z INFO  (e4f5g6) payments-api Method: POST Resource: /v1/payments
2025-04-01T05:10:32.100Z INFO  (e4f5g6) Endpoint: https://payment-processor.internal/process
2025-04-01T05:11:02.200Z ERROR (e4f5g6) Execution failed: Integration Timeout 29000ms
2025-04-01T05:11:02.201Z ERROR (e4f5g6) Method completed with status: 504
2025-04-01T05:11:03.000Z INFO  (h7i8j9) payments-api Method: GET Resource: /v1/health
2025-04-01T05:11:03.050Z INFO  (h7i8j9) Method completed with status: 200
2025-04-01T05:11:04.000Z INFO  (k1l2m3) payments-api Method: POST Resource: /v1/payments
2025-04-01T05:11:34.200Z ERROR (k1l2m3) Execution failed: Integration Timeout 29000ms
"""
    }
}


# ─────────────────────────────────────────
# FUNCTION 1: detect_aws_service_context
# Identifies AWS service type from log group
# Adds service-specific context to prompt
# ─────────────────────────────────────────
def detect_aws_service_context(service_type):
    """
    Returns service-specific context for the prompt.
    Helps LLM give more accurate AWS-specific guidance.
    """
    contexts = {
        "Lambda": (
            "Lambda functions have max 15 min timeout and "
            "128MB-10GB memory. Check Duration and Memory in "
            "REPORT lines. Cold starts add latency. "
            "Timeouts = 504 to callers."
        ),
        "ECS": (
            "ECS containers run in tasks. Exit code 137 = "
            "OOMKill. Health check failures trigger restarts. "
            "Check memory limits in task definition. "
            "Java apps need explicit heap size settings."
        ),
        "API Gateway": (
            "API Gateway has 29 second max integration timeout. "
            "504 = backend timeout. 502 = bad gateway response. "
            "RequestId in parentheses links related log lines. "
            "Health endpoint 200 means gateway itself is fine."
        ),
        "RDS": (
            "RDS slow query logs show queries above threshold. "
            "Check indexes, query plans, connection pool size. "
            "Aurora has different metrics than RDS MySQL/Postgres."
        )
    }
    return contexts.get(service_type, "AWS managed service logs.")


# ─────────────────────────────────────────
# FUNCTION 2: build_cloudwatch_prompt
# Builds prompt with AWS service context
# ─────────────────────────────────────────
def build_cloudwatch_prompt(log_data):
    """
    Builds CloudWatch analysis prompt.
    Injects service-specific AWS context.
    """
    service_context = detect_aws_service_context(
        log_data["service_type"]
    )

    return f"""
You are a senior AWS SRE engineer.
Analyze these CloudWatch logs and return ONLY valid JSON.

AWS Service Context:
{service_context}

Return this exact structure:
{{
  "service_type": "{log_data['service_type']}",
  "log_group": "{log_data['log_group']}",
  "error_count": <number of ERROR lines>,
  "warning_count": <number of WARN lines>,
  "root_cause": "<one sentence root cause>",
  "aws_specific_issue": "<AWS-specific problem e.g. Lambda timeout, ECS OOMKill>",
  "affected_requests": "<number of failed requests if determinable>",
  "severity": "<P1, P2 or P3>",
  "immediate_actions": [
    "<AWS console action or CLI command 1>",
    "<action 2>",
    "<action 3>"
  ],
  "aws_cli_commands": [
    "<relevant aws cli command 1>",
    "<relevant aws cli command 2>"
  ],
  "fix_recommendation": "<what needs to change to fix this permanently>"
}}

Rules:
- Return JSON only. No text before or after.
- aws_cli_commands must use real aws CLI syntax
- P1 if service completely failing all requests
- P2 if partial failures or performance issues
- immediate_actions must include both AWS console and CLI options

Log Group: {log_data['log_group']}
Region: {log_data['region']}
Service: {log_data['service_type']}

CloudWatch Logs:
{log_data['logs']}
"""


# ─────────────────────────────────────────
# FUNCTION 3: call_llm
# Standard Groq call
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
                        "You are a senior AWS SRE engineer. "
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
# FUNCTION 4: format_cloudwatch_output
# Prints formatted CloudWatch analysis
# Shows AWS CLI commands prominently
# ─────────────────────────────────────────
def format_cloudwatch_output(result, log_name):
    """Prints formatted CloudWatch analysis."""
    severity = result.get("severity", "P3")
    emojis = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}
    emoji = emojis.get(severity, "⚪")

    print(f"\n{'='*60}")
    print(f"{emoji}  CloudWatch Analysis: {log_name.upper()}")
    print(f"    Log Group : {result.get('log_group','unknown')}")
    print(f"    Service   : {result.get('service_type','unknown')}")
    print(f"{'='*60}")
    print(f"Severity         : {severity}")
    print(f"Errors           : {result.get('error_count', 0)}")
    print(f"Warnings         : {result.get('warning_count', 0)}")
    print(f"Failed Requests  : {result.get('affected_requests', 'unknown')}")
    print(f"\nRoot Cause       : {result.get('root_cause','unknown')}")
    print(f"AWS Issue        : {result.get('aws_specific_issue','unknown')}")

    actions = result.get("immediate_actions", [])
    if actions:
        print(f"\nImmediate Actions:")
        for i, a in enumerate(actions, 1):
            print(f"  {i}. {a}")

    cli_cmds = result.get("aws_cli_commands", [])
    if cli_cmds:
        print(f"\nAWS CLI Commands:")
        for cmd in cli_cmds:
            print(f"  $ {cmd}")

    print(f"\nFix              : {result.get('fix_recommendation','unknown')}")


# ─────────────────────────────────────────
# FUNCTION 5: analyze_cloudwatch_logs
# Main orchestrator
# ─────────────────────────────────────────
def analyze_cloudwatch_logs(log_data, log_name="unknown"):
    """Full CloudWatch analysis pipeline."""
    print(f"\nAnalyzing: {log_name}")
    print(f"Log Group: {log_data['log_group']}")

    prompt = build_cloudwatch_prompt(log_data)
    result = call_llm(prompt)

    if result:
        format_cloudwatch_output(result, log_name)
        return result
    else:
        print(f"Analysis failed for {log_name}")
        return None


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("AWS CloudWatch Log Analyzer — Starting")
    print("Powered by Groq + LLaMA 3.3\n")

    results = {}

    for log_name, log_data in CLOUDWATCH_LOGS.items():
        result = analyze_cloudwatch_logs(log_data, log_name)
        if result:
            results[log_name] = result

    print(f"\n{'='*60}")
    print(f"Done. Analyzed {len(results)}/3 log groups.")

    print(f"\nSUMMARY:")
    for name, result in results.items():
        sev = result.get("severity", "unknown")
        issue = result.get("aws_specific_issue", "unknown")
        print(f"  {name:30} → {sev} | {issue[:40]}")