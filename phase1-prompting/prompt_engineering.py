from google import genai
from google.genai import types
import os
import json 
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# This is a real Kubernetes log line you would see in production
# Similar to what you see at JPMC
sample_log = """
Back-off restarting failed container
Error: failed to create containerd task: failed to create shim:
OCI runtime create failed: container_linux.go:380:
starting container process caused: process_linux.go:545:
container init caused: rootfs_mount failed:
permission denied: unknown
Exit code: 1
Pod: payment-service-7d9f8b-xk2pl
Namespace: production
Restarts: 8
"""

# ─────────────────────────────────────────
# PROMPT 1 — Vague (bad practice)
# Notice: no structure, no format requirement
# ─────────────────────────────────────────
vague_prompt = "What is wrong with this Kubernetes pod log?"

# ─────────────────────────────────────────
# PROMPT 2 — Engineered (good practice)
# Notice: clear role, exact JSON structure,
# strict instruction to not add extra text
# ─────────────────────────────────────────
engineered_prompt = f"""
You are a senior SRE engineer. Analyze the Kubernetes log below.

Return ONLY a valid JSON object with exactly these fields:
- error_type: category of the error in 3 words or less
- affected_component: pod or service name from the log
- root_cause: one sentence, plain English explanation
- fix_command: the exact kubectl command to investigate
- severity: must be exactly P1, P2 or P3
- confidence: High, Medium or Low based on how clear the log is

Rules:
- Return JSON only. No explanation before or after.
- Never guess if information is not in the log — use "unknown"
- fix_command must be a real kubectl command

Log to analyze:
{sample_log}
"""

print("=" * 60)
print("PROMPT 1 — VAGUE (see why this is unpredictable)")
print("=" * 60)

response1 = client.models.generate_content (
    model = "gemini-2.5-flash",
    config = types.GenerateContentConfig (
        system_instruction = "You are an SRE engineer.",
        temperature = 0,
    ),
    contents = vague_prompt + "\n\n" + sample_log

)
print(response1.text)

print("\n" + "=" * 60)
print("PROMPT 2 — ENGINEERED (structured, reliable)")
print("=" * 60)

response2 = client.models.generate_content(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction="You are a senior SRE engineer. Always return valid JSON only. No markdown, no explanation.",
        temperature=0,
    ),
    contents=engineered_prompt
)
print(response2.text)

# ─────────────────────────────────────────
# Now parse the JSON and use specific fields
# This is what your real tools will do
# ─────────────────────────────────────────
print("\n" + "=" * 60)
print("PARSING JSON OUTPUT — using specific fields")
print("=" * 60)

try:
    # Clean the response in case Gemini adds ```json markers
    # strip() removes leading/trailing spaces
    # replace() removes markdown code fences if present
    raw = response2.text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    # Parse JSON string into Python dictionary
    parsed = json.loads(raw)

    # Now access individual fields exactly like a dict
    print(f"Error Type   : {parsed['error_type']}")
    print(f"Component    : {parsed['affected_component']}")
    print(f"Severity     : {parsed['severity']}")
    print(f"Root Cause   : {parsed['root_cause']}")
    print(f"Fix Command  : {parsed['fix_command']}")
    print(f"Confidence   : {parsed['confidence']}")

    # This is how your Slack alert would use this data
    slack_message = f"""
🚨 *{parsed['severity']} Alert — {parsed['error_type']}*
*Component:* {parsed['affected_component']}
*Root Cause:* {parsed['root_cause']}
*Action:* `{parsed['fix_command']}`
    """
    print("\nSlack message preview:")
    print(slack_message)

except json.JSONDecodeError as e:
    print(f"JSON parsing failed: {e}")
    print("Raw response was:", response2.text)