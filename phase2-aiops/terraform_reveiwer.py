"""
Terraform Plan Reviewer
=======================
Analyzes terraform plan output using Gemini AI.
Returns risk score, security concerns, cost impact,
and approve/review/block recommendation.

Especially useful in banking environments where
IAM changes, security group modifications, and
resource deletions need careful review.

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 8
"""

import json
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
import time 
from groq import Groq

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─────────────────────────────────────────
# SAMPLE TERRAFORM PLANS
# 3 scenarios — safe, risky, critical
# Similar to what you see at JPMC
# ─────────────────────────────────────────

TERRAFORM_PLANS = {

    # SCENARIO 1: Safe change — adding a new EC2 instance
    "safe_change": """
Terraform will perform the following actions:

  # aws_instance.app_server will be created
  + resource "aws_instance" "app_server" {
      + ami                    = "ami-0c55b159cbfafe1f0"
      + instance_type          = "t3.micro"
      + tags                   = {
          + "Environment" = "staging"
          + "Team"        = "payments"
        }
      + vpc_security_group_ids = ["sg-0123456789abcdef0"]
    }

  # aws_cloudwatch_metric_alarm.cpu will be created
  + resource "aws_cloudwatch_metric_alarm" "cpu" {
      + alarm_name  = "high-cpu-staging"
      + metric_name = "CPUUtilization"
      + threshold   = "80"
    }

Plan: 2 to add, 0 to change, 0 to destroy.
""",

    # SCENARIO 2: Risky change — security group opened to internet
    "risky_change": """
Terraform will perform the following actions:

  # aws_security_group.payment_api will be updated in-place
  ~ resource "aws_security_group" "payment_api" {
        id   = "sg-0abc123def456789"
        name = "payment-api-sg"
      ~ ingress {
          ~ cidr_blocks = [
              - "10.0.0.0/8",
              + "0.0.0.0/0",
            ]
            from_port   = 443
            protocol    = "tcp"
            to_port     = 443
        }
    }

  # aws_iam_role_policy.payments will be updated in-place
  ~ resource "aws_iam_role_policy" "payments" {
      ~ policy = jsonencode({
          ~ Statement = [
              ~ {
                  ~ Action   = [
                      + "s3:*",
                      + "dynamodb:*",
                    ]
                    Effect   = "Allow"
                  ~ Resource = "*"
                }
            ]
        })
    }

Plan: 0 to add, 2 to change, 0 to destroy.
""",

    # SCENARIO 3: Critical change — production resource deletion
    "critical_change": """
Terraform will perform the following actions:

  # aws_s3_bucket.payments_data will be destroyed
  - resource "aws_s3_bucket" "payments_data" {
      - bucket        = "jpmc-payments-data-prod"
      - force_destroy = false
      - tags          = {
          - "Environment" = "production"
          - "DataClass"   = "confidential"
        }
    }

  # aws_db_instance.payments_rds will be updated in-place
  ~ resource "aws_db_instance" "payments_rds" {
      ~ deletion_protection = true -> false
      ~ backup_retention_period = 7 -> 0
    }

  # aws_kms_key.encryption will be destroyed
  - resource "aws_kms_key" "encryption" {
      - description = "payments data encryption key"
      - enable_key_rotation = true
    }

Plan: 0 to add, 1 to change, 2 to destroy.
"""
}


# ─────────────────────────────────────────
# FUNCTION 1: parse_plan_summary
# Extracts add/change/destroy counts
# from the last line of terraform plan
# ─────────────────────────────────────────
def parse_plan_summary(plan_text):
    """
    Parses the Plan: X to add, Y to change,
    Z to destroy line from terraform plan output.
    Returns dict with counts.
    """
    # Split plan into lines and search from bottom
    # The summary line is always near the end
    lines = plan_text.strip().split('\n')

    for line in reversed(lines):
        # Look for the summary line
        if 'Plan:' in line and 'to add' in line:
            # Extract numbers using basic string parsing
            # Example: "Plan: 2 to add, 0 to change, 1 to destroy."
            parts = line.replace('Plan:', '').replace('.', '').strip()
            summary = {}

            for part in parts.split(','):
                part = part.strip()
                if 'to add' in part:
                    summary['to_add'] = int(part.split()[0])
                elif 'to change' in part:
                    summary['to_change'] = int(part.split()[0])
                elif 'to destroy' in part:
                    summary['to_destroy'] = int(part.split()[0])

            return summary

    # Return zeros if summary line not found
    return {'to_add': 0, 'to_change': 0, 'to_destroy': 0}


# ─────────────────────────────────────────
# FUNCTION 2: build_terraform_prompt
# Builds risk review prompt with
# banking-specific security rules
# ─────────────────────────────────────────
def build_terraform_prompt(plan_text, summary):
    """
    Builds an engineered prompt for Terraform
    plan risk analysis. Includes banking-specific
    security concerns relevant to JPMC environment.
    """
    return f"""
You are a senior DevOps engineer and cloud security expert
at a financial services company.

Review this Terraform plan and return ONLY valid JSON.

Return this exact structure:
{{
  "risk_score": <number 1-10, where 10 is highest risk>,
  "risk_level": "<Low, Medium, High or Critical>",
  "resources_added": {summary.get('to_add', 0)},
  "resources_changed": {summary.get('to_change', 0)},
  "resources_destroyed": {summary.get('to_destroy', 0)},
  "security_concerns": ["<concern 1>", "<concern 2>"],
  "data_risk": "<None, Low, Medium, High or Critical>",
  "cost_impact": "<Increase, Decrease, Neutral or Unknown>",
  "recommendation": "<Approve, Review Required or Block>",
  "reason": "<one sentence explaining recommendation>",
  "action_required": "<what the engineer must do before applying>"
}}

Banking environment security rules — flag these as HIGH RISK:
- Any security group change to 0.0.0.0/0 (open to internet)
- Any IAM role or policy modification
- Any resource destruction in production
- Disabling encryption or key rotation
- Disabling backup or deletion protection
- S3 bucket becoming publicly accessible
- Any change tagged Environment=production

Rules:
- Return JSON only. No text before or after.
- recommendation must be Block if to_destroy > 0
- recommendation must be Block if any 0.0.0.0/0 change detected
- risk_score 1-3 = Low, 4-6 = Medium, 7-8 = High, 9-10 = Critical
- security_concerns must list specific resource names from the plan

Terraform plan to review:
{plan_text}
"""

'''
# ─────────────────────────────────────────
# FUNCTION 3: call_gemini
# Standard Gemini call — same pattern
# ─────────────────────────────────────────
def call_gemini(prompt):
    """Sends prompt to Gemini, returns parsed JSON."""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=(
                "You are a senior cloud security engineer. "
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


def call_gemini(prompt):
    models_to_try = [
        "gemini-2.0-flash-001",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
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
                raw = response.text.strip()
                raw = raw.replace("```json","").replace("```","").strip()
                return json.loads(raw)
            except Exception as e:
                print(f"Model {model_name} attempt {attempt+1} failed: {e}")
                time.sleep(20)
    return None
'''

def call_gemini(prompt):
    """
    Uses Groq API with Llama3 model.
    Same interface as before — returns parsed JSON dict.
    Groq is free with generous limits.
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
        raw = raw.replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Groq call failed: {e}")
        return None

# ─────────────────────────────────────────
# FUNCTION 4: format_review_output
# Prints formatted risk review to terminal
# ─────────────────────────────────────────
def format_review_output(result, plan_name):
    """Prints formatted risk review report."""

    risk_level = result.get('risk_level', 'Unknown')
    recommendation = result.get('recommendation', 'Review Required')

    # Emoji based on risk level
    risk_emojis = {
        'Low': '🟢',
        'Medium': '🟡',
        'High': '🟠',
        'Critical': '🔴'
    }
    rec_emojis = {
        'Approve': '✅',
        'Review Required': '⚠️',
        'Block': '🚫'
    }

    risk_emoji = risk_emojis.get(risk_level, '⚪')
    rec_emoji = rec_emojis.get(recommendation, '⚠️')

    print(f"\n{'='*60}")
    print(f"TERRAFORM PLAN REVIEW: {plan_name.upper()}")
    print(f"{'='*60}")
    print(f"Risk Score    : {result.get('risk_score')}/10")
    print(f"Risk Level    : {risk_emoji} {risk_level}")
    print(f"Recommendation: {rec_emoji} {recommendation}")
    print(f"\nChanges:")
    print(f"  + Added   : {result.get('resources_added', 0)}")
    print(f"  ~ Changed : {result.get('resources_changed', 0)}")
    print(f"  - Destroyed: {result.get('resources_destroyed', 0)}")
    print(f"\nData Risk     : {result.get('data_risk', 'Unknown')}")
    print(f"Cost Impact   : {result.get('cost_impact', 'Unknown')}")
    print(f"\nReason:")
    print(f"  {result.get('reason', 'unknown')}")

    concerns = result.get('security_concerns', [])
    if concerns:
        print(f"\nSecurity Concerns:")
        for concern in concerns:
            print(f"  ⚠️  {concern}")

    action = result.get('action_required', '')
    if action:
        print(f"\nAction Required:")
        print(f"  → {action}")


# ─────────────────────────────────────────
# FUNCTION 5: review_terraform_plan
# Main orchestrator function
# ─────────────────────────────────────────
def review_terraform_plan(plan_text, plan_name="unknown"):
    """
    Full Terraform plan review pipeline.
    Returns risk assessment dict or None.
    """
    print(f"\nReviewing plan: {plan_name}")

    # Step 1: Parse summary counts from plan
    summary = parse_plan_summary(plan_text)
    print(f"Changes: +{summary.get('to_add',0)} "
          f"~{summary.get('to_change',0)} "
          f"-{summary.get('to_destroy',0)}")

    # Step 2: Build risk review prompt
    prompt = build_terraform_prompt(plan_text, summary)

    # Step 3: Get AI risk assessment
    result = call_gemini(prompt)

    if result:
        # Step 4: Print formatted output
        format_review_output(result, plan_name)
        return result
    else:
        print(f"Review failed for {plan_name}")
        return None


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("Terraform Plan Reviewer — Starting")
    print("Powered by Gemini AI\n")

    results = {}

    for plan_name, plan_text in TERRAFORM_PLANS.items():
        result = review_terraform_plan(plan_text, plan_name)
        if result:
            results[plan_name] = result

    print(f"\n{'='*60}")
    print(f"Review complete. Processed {len(results)}/3 plans.")

    # Summary of recommendations
    print(f"\nRECOMMENDATION SUMMARY:")
    for name, result in results.items():
        rec = result.get('recommendation', 'Unknown')
        risk = result.get('risk_level', 'Unknown')
        print(f"  {name:20} → {rec:20} (Risk: {risk})")