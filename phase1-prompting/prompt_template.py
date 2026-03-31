import json
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ─────────────────────────────────────────
# PROMPT LIBRARY CLASS
# One place for all your SRE prompts
# Add new templates here as you build more tools
# ─────────────────────────────────────────
class PromptLibrary:
    """
    Central library of all SRE prompt templates.
    Each template has placeholders filled at runtime
    using Python's .format(**kwargs) method.
    """

    TEMPLATES = {

        # ── TEMPLATE 1: Kubernetes Log Analyzer ──
        # Used in: k8s_log_analyzer.py (Day 3)
        # Placeholders: {log_content}
        "k8s_log": """
You are a senior SRE engineer at a fintech company.
Analyze the Kubernetes log below and return ONLY valid JSON.

Return this exact structure:
{{
  "error_type": "type of error in 3 words or less",
  "affected_component": "pod or service name from log",
  "root_cause": "one sentence plain English explanation",
  "immediate_action": "exact kubectl command to run first",
  "fix": "how to permanently resolve this",
  "severity": "P1, P2 or P3",
  "confidence": "High, Medium or Low"
}}

Rules:
- Return JSON only. No text before or after.
- Use "unknown" if information is not in the log.
- P1 = service down, P2 = degraded, P3 = warning.

Log to analyze:
{log_content}
""",

        # ── TEMPLATE 2: Alert Triage ──
        # Used in: alert_summarizer.py (Day 10)
        # Placeholders: {alert_name}, {severity},
        #               {labels}, {description}
        "alert_triage": """
You are a senior SRE on-call engineer at a fintech company.
Triage the following alert and return ONLY valid JSON.

Return this exact structure:
{{
  "alert_name": "name of the alert",
  "severity": "P1, P2 or P3",
  "summary": "one sentence plain English summary",
  "probable_cause": "most likely root cause",
  "immediate_steps": ["step 1", "step 2", "step 3"],
  "affected_service": "service or component name",
  "escalate": true or false
}}

Alert Details:
- Name: {alert_name}
- Severity: {severity}
- Labels: {labels}
- Description: {description}

Rules:
- Return JSON only. No text before or after.
- escalate must be true if severity is P1 or unknown.
- immediate_steps must always have exactly 3 steps.
""",

        # ── TEMPLATE 3: Terraform Plan Reviewer ──
        # Used in: terraform_reviewer.py (Day 8)
        # Placeholders: {plan_output}
        "terraform_review": """
You are a senior DevOps engineer and cloud security expert.
Review the Terraform plan below and return ONLY valid JSON.

Return this exact structure:
{{
  "risk_score": "1 to 10 where 10 is highest risk",
  "risk_level": "Low, Medium, High or Critical",
  "resources_added": "number of resources being added",
  "resources_changed": "number of resources being changed",
  "resources_destroyed": "number of resources being destroyed",
  "security_concerns": ["concern 1", "concern 2"],
  "cost_impact": "estimated cost change if determinable",
  "recommendation": "Approve, Review Required or Block",
  "reason": "one sentence explaining the recommendation"
}}

Rules:
- Return JSON only. No text before or after.
- Flag any IAM changes, security group changes, or destroy operations.
- In a banking environment flag anything touching encryption or data storage.
- recommendation must be Block if any resource is being destroyed in production.

Terraform plan:
{plan_output}
""",

        # ── TEMPLATE 4: Splunk Log Analyzer ──
        # Used in: splunk_analyzer.py (Phase 2)
        # Placeholders: {log_content}, {time_range}
        "splunk_log": """
You are a senior SRE engineer. Analyze the Splunk logs below.
Time range: {time_range}

Return ONLY valid JSON with this exact structure:
{{
  "error_count": "number of ERROR level entries",
  "warning_count": "number of WARN level entries",
  "top_errors": ["error 1", "error 2", "error 3"],
  "affected_services": ["service 1", "service 2"],
  "time_of_first_error": "timestamp if available",
  "pattern": "description of error pattern or trend",
  "severity": "P1, P2 or P3",
  "recommended_action": "what to investigate first"
}}

Rules:
- Return JSON only. No text before or after.
- top_errors must be the 3 most frequent or impactful errors.
- If no errors found set error_count to 0 and severity to P3.

Splunk logs:
{log_content}
""",

        # ── TEMPLATE 5: CI/CD Failure Analyzer ──
        # Used in: cicd_analyzer.py (Phase 2)
        # Placeholders: {pipeline_name}, {stage},
        #               {error_log}
        "cicd_failure": """
You are a senior DevOps engineer. Analyze this CI/CD pipeline failure.
Pipeline: {pipeline_name}
Failed Stage: {stage}

Return ONLY valid JSON with this exact structure:
{{
  "failure_type": "type of failure in 3 words",
  "failed_stage": "name of the stage that failed",
  "root_cause": "one sentence explanation",
  "fix_command": "command or config change to fix this",
  "prevention": "how to prevent this in future",
  "severity": "P1, P2 or P3",
  "retry_safe": true or false
}}

Rules:
- Return JSON only. No text before or after.
- retry_safe is true only if the failure is transient
  like a network timeout or flaky test.
- retry_safe is false for config errors or missing files.

Error log:
{error_log}
"""
    }

    def get(self, template_name, **kwargs):
        """
        Gets a template by name and fills in placeholders.

        Usage:
            library = PromptLibrary()
            prompt = library.get("k8s_log", log_content=my_log)

        Args:
            template_name: key from TEMPLATES dict
            **kwargs: placeholder values to fill in

        Returns:
            Filled prompt string ready to send to Gemini
        """
        if template_name not in self.TEMPLATES:
            raise ValueError(
                f"Template '{template_name}' not found. "
                f"Available: {list(self.TEMPLATES.keys())}"
            )

        template = self.TEMPLATES[template_name]

        # .format(**kwargs) replaces all {placeholders}
        # with the values you passed in
        return template.format(**kwargs)

    def list_templates(self):
        """Returns list of all available template names."""
        return list(self.TEMPLATES.keys())


# ─────────────────────────────────────────
# TEST THE LIBRARY
# Call each template with sample data
# Verify the output is correct JSON
# ─────────────────────────────────────────
def call_gemini(prompt):
    """Helper function — sends any prompt to Gemini."""
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
    raw = response.text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


if __name__ == "__main__":
    library = PromptLibrary()

    print("Available templates:", library.list_templates())
    print("\n" + "="*60)

    # ── TEST 1: Kubernetes log template ──
    print("\nTEST 1: Kubernetes Log Template")
    print("="*60)

    sample_k8s_log = """
    OOMKilled: container memory limit exceeded
    Pod: payment-service-7d9f8b-xk2pl
    Namespace: production
    Memory limit: 512Mi
    Memory usage: 514Mi
    Restarts: 4
    """

    # Get filled prompt from library
    prompt = library.get("k8s_log", log_content=sample_k8s_log)
    result = call_gemini(prompt)
    print(json.dumps(result, indent=2))

    # ── TEST 2: Alert triage template ──
    print("\nTEST 2: Alert Triage Template")
    print("="*60)

    prompt = library.get(
        "alert_triage",
        alert_name="HighCPUUsage",
        severity="critical",
        labels="env=production, service=payment-api",
        description="CPU usage above 90% for 5 minutes on payment-api"
    )
    result = call_gemini(prompt)
    print(json.dumps(result, indent=2))

    print("\n" + "="*60)
    print("Template library working correctly.")
    print("All future tools will import from this library.")