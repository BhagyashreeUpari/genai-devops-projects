# GenAI for DevOps & SRE

> A collection of AI-powered tools built on top of real DevOps and SRE workflows.
> Built using Python and Google Gemini API.

**Author:** Bhagyashree  
**Role:** SRE/DevOps Engineer  
**Company:** JPMC, Bangalore  
**Started:** April 2025

---

## 🎯 Why This Project Exists

Modern SRE and DevOps teams are drowning in alerts, logs, and incidents.
This project applies GenAI to automate the intelligence layer —
so engineers spend less time reading logs and more time fixing systems.

Every tool here is built to solve a real problem I encounter daily
working with Kubernetes, Prometheus, Dynatrace, Splunk,
Terraform, Spinnaker, and Jenkins.

---

## 🛠️ Tech Stack

| Category | Tools |
|---|---|
| AI/LLM | Google Gemini API (gemini-2.5-flash) |
| Language | Python 3.9+ |
| DevOps Tools | Kubernetes, Docker, AWS, Terraform |
| Monitoring | Prometheus, Grafana, Dynatrace, Splunk |
| CI/CD | Spinnaker, Jenkins, GitHub Actions |
| Libraries | google-genai, python-dotenv |

---

## 📁 Project Structure
```
genai-devops-projects/
├── phase1-prompting/        # GenAI foundations + first SRE tools
│   ├── hello_gemini_v1.py   # First Gemini API call + temperature
│   ├── list_models.py       # Model discovery utility
│   ├── prompt_engineering.py # Vague vs engineered prompts
│   ├── k8s_log_analyzer.py  # Kubernetes log analyzer tool
│   ├── prompt_templates.py  # Central prompt template library
│   └── requirements.txt     # Python dependencies
├── phase2-aiops/            # AIOps + monitoring integration
├── phase3-incident/         # Incident response automation
└── phase4-cicd/             # CI/CD pipeline AI tools
```

---

## ✅ Phase 1 — Tools Built (Week 1)

### 1. Kubernetes Log Analyzer
**File:** `phase1-prompting/k8s_log_analyzer.py`

Analyzes raw Kubernetes pod logs and returns structured diagnosis.

**Supports:**
- CrashLoopBackOff
- OOMKilled
- ImagePullBackOff

**Output:**
```json
{
  "error_type": "OOMKilled",
  "affected_component": "payment-service",
  "root_cause": "Container exceeded 512Mi memory limit",
  "immediate_action": "kubectl describe pod payment-service-xxx -n production",
  "fix": "Increase memory limit or fix memory leak in application",
  "severity": "P1",
  "confidence": "High"
}
```

---

### 2. SRE Prompt Template Library
**File:** `phase1-prompting/prompt_templates.py`

Central library of reusable AI prompt templates.
All tools import from here — one place to manage all prompts.

**Templates available:**
- `k8s_log` — Kubernetes log analysis
- `alert_triage` — Prometheus/Dynatrace/Splunk alert triage
- `terraform_review` — Terraform plan risk assessment
- `splunk_log` — Splunk log analysis
- `cicd_failure` — CI/CD pipeline failure diagnosis

---

## 🚀 How to Run
```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/genai-devops-projects.git
cd genai-devops-projects/phase1-prompting

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
echo "GEMINI_API_KEY=your_key_here" > .env

# 5. Run the Kubernetes log analyzer
python k8s_log_analyzer.py
```

---

## 📈 Roadmap

- [x] Phase 1: GenAI foundations + Kubernetes log analyzer
- [ ] Phase 2: AIOps — alert summarizer + Slack integration
- [ ] Phase 3: Incident response automation
- [ ] Phase 4: CI/CD pipeline AI tools

---

## 🎯 Career Goal

Building this portfolio for
SRE/DevOps Engineer
with GenAI specialisation.

Target: Internal JPMC switch or external role by end of 2026.