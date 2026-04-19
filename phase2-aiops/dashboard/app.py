"""
AIOps Dashboard
===============
Flask web UI combining all Phase 2 tools.
Single interface for alert analysis, log
analysis, terraform review and CI/CD diagnosis.

Part of : GenAI for DevOps & SRE — Phase 2
Author  : Bhagyashree
Day     : 14
"""

import sys
import os
import json
from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv

# Add parent directory to path so we can import our tools
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = Flask(__name__)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ─────────────────────────────────────────
# SHARED LLM CALL FUNCTION
# ─────────────────────────────────────────
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
        return {"error": str(e)}


# ─────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/analyze-alert', methods=['POST'])
def analyze_alert():
    """
    Analyzes a Prometheus or Dynatrace alert.
    Input: JSON with alert fields
    Output: enriched diagnosis JSON
    """
    data = request.json
    alert_text = data.get('alert_text', '')

    prompt = f"""
You are a senior SRE on-call engineer.
Analyze this alert and return ONLY valid JSON:
{{
  "severity": "P1, P2 or P3",
  "summary": "one sentence plain English summary",
  "probable_cause": "most likely root cause",
  "immediate_steps": ["step 1", "step 2", "step 3"],
  "escalate": true or false,
  "escalate_reason": "why escalation is needed if true"
}}

Alert:
{alert_text}
"""
    result = call_llm(prompt)
    return jsonify(result)


@app.route('/analyze-log', methods=['POST'])
def analyze_log():
    """
    Analyzes Kubernetes or Splunk logs.
    Input: JSON with log_text and log_type
    Output: structured diagnosis JSON
    """
    data = request.json
    log_text = data.get('log_text', '')
    log_type = data.get('log_type', 'kubernetes')

    prompt = f"""
You are a senior SRE engineer analyzing {log_type} logs.
Return ONLY valid JSON:
{{
  "error_count": <number>,
  "severity": "P1, P2 or P3",
  "root_cause": "one sentence root cause",
  "top_errors": ["error 1", "error 2", "error 3"],
  "affected_services": ["service 1", "service 2"],
  "recommended_action": "most important action to take"
}}

Logs:
{log_text}
"""
    result = call_llm(prompt)
    return jsonify(result)


@app.route('/review-terraform', methods=['POST'])
def review_terraform():
    """
    Reviews Terraform plan for risks.
    Input: JSON with plan_text
    Output: risk assessment JSON
    """
    data = request.json
    plan_text = data.get('plan_text', '')

    prompt = f"""
You are a senior DevOps engineer and cloud security expert.
Review this Terraform plan and return ONLY valid JSON:
{{
  "risk_score": <1-10>,
  "risk_level": "Low, Medium, High or Critical",
  "recommendation": "Approve, Review Required or Block",
  "security_concerns": ["concern 1", "concern 2"],
  "reason": "one sentence explaining recommendation"
}}

Terraform plan:
{plan_text}
"""
    result = call_llm(prompt)
    return jsonify(result)


@app.route('/analyze-cicd', methods=['POST'])
def analyze_cicd():
    """
    Analyzes CI/CD pipeline failures.
    Input: JSON with error_log and tool name
    Output: failure diagnosis JSON
    """
    data = request.json
    error_log = data.get('error_log', '')
    tool = data.get('tool', 'Jules Pipeline')

    prompt = f"""
You are a senior DevOps engineer analyzing a {tool} failure.
Return ONLY valid JSON:
{{
  "failure_type": "type in 3 words",
  "root_cause": "one sentence explanation",
  "fix_command": "exact fix command or config change",
  "severity": "P1, P2 or P3",
  "retry_safe": true or false,
  "retry_reason": "why safe or unsafe to retry"
}}

Error log:
{error_log}
"""
    result = call_llm(prompt)
    return jsonify(result)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "tools": 4})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)