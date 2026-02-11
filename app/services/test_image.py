import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")

print("OPENAI_KEY loaded:", bool(OPENAI_KEY))

url = "https://api.openai.com/v1/images/generations"

payload = {
    "model": "gpt-image-1",
    "prompt": "Simple school science illustration for children. Metals are shiny and conduct electricity. Cartoon style.",
    "size": "1024x1024"
}

headers = {
    "Authorization": f"Bearer {OPENAI_KEY}",
    "Content-Type": "application/json"
}

resp = requests.post(url, headers=headers, json=payload)

print("STATUS:", resp.status_code)
print("RESPONSE TEXT:\n", resp.text[:2000])  # first 2000 chars
