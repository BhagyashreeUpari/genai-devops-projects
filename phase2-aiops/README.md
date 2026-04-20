# Phase 2 — AIOps Tools

AI-powered DevOps and SRE tools built on top of 
real enterprise monitoring and operations stack.

**LLM:** Groq + LLaMA 3.3 70B  
**Author:** Bhagyashree | JPMC Bangalore

---

## Tools Built

| Tool | File | What It Does |
|---|---|---|
| Alert Summarizer | alert_summarizer_v2.py | Prometheus/Dynatrace alerts → Slack |
| Terraform Reviewer | terraform_reviewer.py | Risk analysis with banking rules |
| Splunk Analyzer | splunk_analyzer.py | Error patterns + circuit breaker detection |
| CI/CD Failure Analyzer | cicd_failure_analyzer.py | Jules + Jenkins failure diagnosis |
| PromQL Assistant | prometheus_grafana_ai.py | Plain English → PromQL queries |
| Dashboard Narrator | prometheus_grafana_ai.py | Metrics → executive summary |
| Dynatrace Handler | dynatrace_handler.py | Davis AI problem enrichment |
| CloudWatch Analyzer | cloudwatch_analyzer.py | Lambda/ECS/API Gateway logs |
| AIOps Dashboard | dashboard/app.py | Web UI combining all tools |

---

## How to Run

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Add API key to .env
echo "GROQ_API_KEY=your_key" > .env

# Run any tool
python alert_summarizer_v2.py
python terraform_reviewer.py

# Run web dashboard
cd dashboard && python app.py
# Open http://localhost:5000
```

---

## Stack

- **AI/LLM:** Groq API, LLaMA 3.3 70B (free tier)
- **Monitoring:** Prometheus, Grafana, Dynatrace, Splunk, CloudWatch
- **Infrastructure:** Kubernetes, Terraform, AWS
- **CI/CD:** Jules Pipeline, Jenkins
- **Web:** Flask, Bootstrap 5