from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        system_instruction="You are a senior SRE engineer at a fintech company. Always be concise and practical. Focus on actionable steps.",
        temperature=0,
    ),
    contents="What are the top 3 things to check first when a Kubernetes pod is in CrashLoopBackOff?"
)

print(response.text)