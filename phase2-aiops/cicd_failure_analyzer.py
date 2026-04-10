"""
CI/CD Failure Analyzer
======================
Analyzes Jules Pipeline and Jenkins CI/CD
failure logs using AI.
Returns failure type, root cause, fix command,
prevention tip and retry safety decision.

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 10
"""

import json
import time
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─────────────────────────────────────────
# SAMPLE PIPELINE FAILURES
# Covers Jules Pipelines (your tool at JPMC)
# and Jenkins (industry standard)
# ─────────────────────────────────────────
PIPELINE_FAILURES = {

    "jules_test_failure": {
        "pipeline_name": "payments-service-deploy",
        "stage": "Unit Tests",
        "tool": "Jules Pipeline",
        "error_log": """
[Jules] Starting pipeline: payments-service-deploy
[Jules] Stage: Build — PASSED (45s)
[Jules] Stage: Unit Tests — RUNNING
[Test] Running 247 tests...
[Test] FAILED: PaymentServiceTest.testTransactionRollback
[Test] Expected: TransactionException but got: NullPointerException
[Test] at PaymentService.processPayment(PaymentService.java:145)
[Test] FAILED: PaymentServiceTest.testRefundProcessing
[Test] NullPointerException: paymentRepository is null
[Test] at PaymentService.processRefund(PaymentService.java:203)
[Test] Results: 245 passed, 2 failed, 0 skipped
[Jules] Stage: Unit Tests — FAILED
[Jules] Pipeline ABORTED — downstream stages skipped
"""
    },

    "jules_deploy_failure": {
        "pipeline_name": "auth-service-release",
        "stage": "Deploy to Production",
        "tool": "Jules Pipeline",
        "error_log": """
[Jules] Starting pipeline: auth-service-release
[Jules] Stage: Build — PASSED (38s)
[Jules] Stage: Unit Tests — PASSED (124s)
[Jules] Stage: Integration Tests — PASSED (89s)
[Jules] Stage: Deploy to Production — RUNNING
[Deploy] Deploying auth-service:v2.3.1 to production
[Deploy] kubectl set image deployment/auth-service auth-service=registry/auth-service:v2.3.1
[Deploy] Waiting for rollout to complete...
[Deploy] Deployment rollout failed: 5/10 pods available
[Deploy] Pod auth-service-7d9f8b-xk2pl — CrashLoopBackOff
[Deploy] Error: new pod containers do not have associated resource limits
[Deploy] Rollback triggered automatically
[Deploy] Rolled back to auth-service:v2.3.0
[Jules] Stage: Deploy to Production — FAILED
[Jules] Pipeline FAILED — rollback completed
"""
    },

    "jenkins_build_failure": {
        "pipeline_name": "fraud-detection-build",
        "stage": "Docker Build",
        "tool": "Jenkins",
        "error_log": """
[Jenkins] Building fraud-detection-build #142
[Jenkins] Stage: Checkout — PASSED
[Jenkins] Stage: Docker Build — RUNNING
[Docker] Building image fraud-detection:latest
[Docker] Step 1/8 : FROM python:3.11-slim
[Docker] Step 2/8 : WORKDIR /app
[Docker] Step 3/8 : COPY requirements.txt .
[Docker] Step 4/8 : RUN pip install -r requirements.txt
[Docker] ERROR: Could not find a version that satisfies
[Docker] the requirement tensorflow==2.14.0
[Docker] ERROR: No matching distribution found
[Docker] The command returned a non-zero code: 1
[Jenkins] Stage: Docker Build — FAILED
[Jenkins] Build #142 FAILED
"""
    },

    "jules_network_failure": {
        "pipeline_name": "reporting-service-deploy",
        "stage": "Pull Docker Image",
        "tool": "Jules Pipeline",
        "error_log": """
[Jules] Starting pipeline: reporting-service-deploy
[Jules] Stage: Pull Docker Image — RUNNING
[Docker] Pulling registry.jpmc.internal/reporting:v1.2.0
[Docker] Error response from daemon:
[Docker] dial tcp 10.0.5.22:443: connect: connection refused
[Docker] Retrying... attempt 1 of 3
[Docker] dial tcp 10.0.5.22:443: connect: connection refused
[Docker] Retrying... attempt 2 of 3
[Docker] dial tcp 10.0.5.22:443: connect: connection refused
[Jules] Stage: Pull Docker Image — FAILED
[Jules] Error: Unable to reach internal registry
[Jules] Pipeline FAILED
"""
    }
}


# ─────────────────────────────────────────
# FUNCTION 1: build_cicd_prompt
# Builds engineered prompt for CI/CD
# failure analysis with Jules awareness
# ─────────────────────────────────────────
def build_cicd_prompt(pipeline_name, stage, tool, error_log):
    """
    Builds structured prompt for CI/CD failure analysis.
    Includes Jules Pipeline and Jenkins specific context.
    """
    return f"""
You are a senior DevOps engineer with expertise in
Jules Pipelines and Jenkins CI/CD systems.

Analyze this pipeline failure and return ONLY valid JSON:
{{
  "failure_type": "<type of failure in 3 words or less>",
  "failed_stage": "<exact stage name that failed>",
  "tool": "<Jules Pipeline or Jenkins>",
  "root_cause": "<one sentence plain English explanation>",
  "fix_command": "<exact command or config change needed>",
  "fix_description": "<plain English explanation of the fix>",
  "prevention": "<how to prevent this failure in future>",
  "severity": "<P1, P2 or P3>",
  "retry_safe": <true or false>,
  "retry_reason": "<why it is or is not safe to retry without fixing>"
}}

Severity rules:
- P1: production deployment failed or rollback triggered
- P2: build or test failure blocking release
- P3: non-critical stage failure

Retry rules:
- retry_safe TRUE only for transient failures:
  network timeouts, flaky tests, temporary registry issues
- retry_safe FALSE for code errors, missing dependencies,
  wrong config, resource limits — these need a fix first

Pipeline details:
- Pipeline : {pipeline_name}
- Tool     : {tool}
- Stage    : {stage}

Return JSON only. No text before or after.

Error log:
{error_log}
"""


# ─────────────────────────────────────────
# FUNCTION 2: call_llm
# Groq API call — same pattern as Day 9
# ─────────────────────────────────────────
def call_llm(prompt):
    """
    Sends prompt to Groq LLaMA model.
    Returns parsed JSON dict or None.
    """
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior DevOps engineer. "
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
# FUNCTION 3: format_cicd_output
# Prints formatted failure analysis
# Shows retry safety prominently
# ─────────────────────────────────────────
def format_cicd_output(result, pipeline_name):
    """
    Prints formatted CI/CD failure analysis.
    Highlights retry safety and fix command.
    """
    severity = result.get('severity', 'P2')
    emojis = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}
    emoji = emojis.get(severity, "⚪")

    retry = result.get('retry_safe', False)
    retry_display = "✅ Safe to retry" if retry else "🚫 Fix required before retry"

    print(f"\n{'='*60}")
    print(f"{emoji}  CI/CD FAILURE: {pipeline_name.upper()}")
    print(f"{'='*60}")
    print(f"Tool         : {result.get('tool', 'unknown')}")
    print(f"Failed Stage : {result.get('failed_stage', 'unknown')}")
    print(f"Failure Type : {result.get('failure_type', 'unknown')}")
    print(f"Severity     : {severity}")
    print(f"Retry        : {retry_display}")
    print(f"\nRoot Cause   : {result.get('root_cause', 'unknown')}")
    print(f"\nFix Command  : {result.get('fix_command', 'unknown')}")
    print(f"Fix Details  : {result.get('fix_description', 'unknown')}")
    print(f"Prevention   : {result.get('prevention', 'unknown')}")
    print(f"Retry Reason : {result.get('retry_reason', 'unknown')}")


# ─────────────────────────────────────────
# FUNCTION 4: analyze_pipeline_failure
# Main orchestrator for CI/CD analysis
# ─────────────────────────────────────────
def analyze_pipeline_failure(failure_data, failure_name="unknown"):
    """
    Full CI/CD failure analysis pipeline.
    Returns analysis dict or None.
    """
    print(f"\nAnalyzing: {failure_name}")
    print(f"Tool: {failure_data['tool']} | Stage: {failure_data['stage']}")

    # Step 1: Build prompt
    prompt = build_cicd_prompt(
        pipeline_name=failure_data['pipeline_name'],
        stage=failure_data['stage'],
        tool=failure_data['tool'],
        error_log=failure_data['error_log']
    )

    # Step 2: Call LLM
    result = call_llm(prompt)

    if result:
        # Step 3: Print formatted output
        format_cicd_output(result, failure_data['pipeline_name'])
        return result
    else:
        print(f"Analysis failed for {failure_name}")
        return None


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("CI/CD Failure Analyzer — Starting")
    print("Covers: Jules Pipelines + Jenkins\n")

    results = {}

    for failure_name, failure_data in PIPELINE_FAILURES.items():
        result = analyze_pipeline_failure(failure_data, failure_name)
        if result:
            results[failure_name] = result
        time.sleep(3)

    print(f"\n{'='*60}")
    print(f"Done. Analyzed {len(results)}/4 failures.")

    print(f"\nRETRY SUMMARY:")
    for name, result in results.items():
        retry = "✅ Retry safe" if result.get('retry_safe') else "🚫 Fix first"
        sev = result.get('severity', 'unknown')
        print(f"  {name:35} → {sev} | {retry}")