from fastapi import HTTPException, APIRouter

from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import requests, os, io, re, base64
from datetime import datetime
from dotenv import load_dotenv
from fastapi import APIRouter

router = APIRouter(tags=["teachback"])

load_dotenv()

PERPLEXITY_KEY = os.getenv("PERPLEXITY_KEY")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")



# -------------------- AUDIO (ElevenLabs) --------------------

def generate_human_voice(text: str):
    if not ELEVENLABS_KEY:
        return None

    response = requests.post(
        "https://api.elevenlabs.io/v1/text-to-speech/EXAVITQu4vr4xnSDxMaL",
        headers={
            "xi-api-key": ELEVENLABS_KEY,
            "Content-Type": "application/json"
        },
        json={
            "text": text,
            "voice_settings": {
                "stability": 0.65,
                "similarity_boost": 0.75
            }
        },
        timeout=30
    )

    if response.status_code != 200:
        print("ElevenLabs Error:", response.text)
        return None

    return response.content


# -------------------- IMAGE (OpenAI) --------------------
# ✅ Returns base64 image

def generate_example_image(prompt: str):
    if not OPENAI_KEY:
        print("OPENAI_API_KEY missing in .env")
        return None

    try:
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {OPENAI_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gpt-image-1",
                "prompt": f"Simple school science illustration for children. {prompt}. Clean, clear, labeled, cartoon style.",
                "size": "1024x1024"
            },
            timeout=60
        )

        if response.status_code != 200:
            print("Image error:", response.text)
            return None

        data = response.json()

        # ✅ gpt-image-1 usually returns b64_json
        b64 = data["data"][0].get("b64_json")
        if not b64:
            print("Image response missing b64_json:", data)
            return None

        # return as data URL
        return f"data:image/png;base64,{b64}"

    except Exception as e:
        print("Image Exception:", e)
        return None


# -------------------- SUPABASE SAVE --------------------

def save_to_supabase(data, speak_text, image_url):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    payload = {
        "student_name": data.student_name,
        "subject": data.subject,
        "class_level": data.class_level,
        "topic": data.topic,
        "student_explanation": data.explanation,
        "analysis": speak_text,
        "image_url": image_url or "",
        "created_at": datetime.utcnow().isoformat()
    }

    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/teach_back_logs",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json=payload,
            timeout=10
        )
    except Exception as e:
        print("Supabase error:", e)


# -------------------- SCHEMA --------------------

class TeachBackRequest(BaseModel):
    student_name: str
    subject: str
    class_level: str
    topic: str
    explanation: str
    language: str
    stage: str = "explain"


# -------------------- CLEAN OUTPUT --------------------

def clean_ai_text(text: str) -> str:
    # remove citations like [1][2][3]
    text = re.sub(r"\[\d+\]", "", text)

    # remove markdown stars
    text = text.replace("**", "").replace("*", "")

    # remove extra spaces
    text = re.sub(r"[ \t]+", " ", text)

    # keep line breaks neat
    text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])

    return text.strip()


# -------------------- PROMPT --------------------

def generate_teachback_prompt(data: TeachBackRequest):

    try:
        class_level = int(data.class_level)
    except:
        class_level = 5

    language = (data.language or "English").strip()

    if language == "Hindi":
        lang_rule = "Reply only in Hindi. Do not mix English."
    elif language == "English":
        lang_rule = "Reply only in English. Do not mix Hindi."
    else:
        lang_rule = "Reply only in Hinglish (natural mix)."

    # style by class
    if class_level <= 4:
        style_rules = "Use very simple words. Max 6 short lines."
    elif class_level <= 6:
        style_rules = "Use simple words. Max 7 short lines."
    else:
        style_rules = "Use clear words. Max 8 short lines."

    teachback_rules = """
You are a friendly school teacher using the Teach-Back method.

STRICT RULES:
- Stay ONLY on the given TOPIC.
- Do NOT give a long lecture.
- Do NOT add citations like [1][2][3].
- Do NOT add hashtags or headings.
- Encourage the student in every message.
- If answer is correct:
  - Praise in 1 line
  - Ask exactly ONE question
- If answer is wrong or incomplete:
  - Say: "Good try" (not harsh)
  - Give correction in 2 lines max
  - Give 1 real-life example in 1 line
  - Ask exactly ONE question
- Always end with exactly ONE question.
- Do NOT use Markdown.
- Do NOT use **bold**, *italics*, # headings, or bullet points.
"""

    return f"""
{lang_rule}

{teachback_rules}

Writing style:
{style_rules}

Student name: {data.student_name}
Class: {class_level}
Subject: {data.subject}
Topic: {data.topic}

Student explanation:
{data.explanation}

Now respond as the tutor.
"""


# -------------------- AI CALL --------------------

def call_perplexity(prompt: str):
    if not PERPLEXITY_KEY:
        raise HTTPException(status_code=500, detail="Missing PERPLEXITY_KEY in .env")

    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {PERPLEXITY_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "sonar-pro",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "top_p": 0.9,
            "return_citations": False
        },
        timeout=30
    )

    if response.status_code != 200:
        print("Perplexity Error:", response.text)
        raise HTTPException(status_code=500, detail="AI error")

    return response.json()


# -------------------- ENDPOINT --------------------

@router.post("/teach-back")
def teach_back(data: TeachBackRequest):

    prompt = generate_teachback_prompt(data)
    result = call_perplexity(prompt)

    raw = result["choices"][0]["message"]["content"]
    speak_text = clean_ai_text(raw)

    # ✅ IMAGE ON EVERY MESSAGE
    image_query = f"{data.topic}. Student said: {data.explanation}. Tutor reply: {speak_text}"
    image_url = generate_example_image(image_query)
    print("OPENAI_KEY present:", bool(OPENAI_KEY))
    print("Image prompt:", prompt)


    # voice
    audio = generate_human_voice(speak_text)

    save_to_supabase(data, speak_text, image_url)

    # ✅ If ElevenLabs missing → JSON
    if not audio:
        return JSONResponse({"speak": speak_text, "image_url": image_url})

    # ✅ Return audio + headers
    return StreamingResponse(
        io.BytesIO(audio),
        media_type="audio/mpeg",
        headers={
            "X-Speak-Text": speak_text,
            "X-Image-Url": image_url or ""
        }
    )
