from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Testing 3 temperature values
# 0   = same answer every time - use this for all SRE automation tools
# 0.5 = balanced
# 1.0 = creative, varies every time - not good for automation

temperatures = [0, 0.5, 1.0]

for temp in temperatures:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            system_instruction="You are an SRE engineer.",
            temperature=temp,
        ),
        contents="In one sentence, describe a cause for high CPU on a Kubernetes node."
    )
    print(f"\n--- Temperature {temp} ---")
    print(response.text)