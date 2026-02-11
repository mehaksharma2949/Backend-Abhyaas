from fastapi.responses import FileResponse
from pydantic import BaseModel
import requests, os, uuid
from datetime import datetime
from dotenv import load_dotenv
from fastapi import APIRouter

router = APIRouter(tags=["Worksheet"])

load_dotenv()

PERPLEXITY_KEY = os.getenv("PERPLEXITY_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


class WorksheetRequest(BaseModel):
    subject: str
    classLevel: str
    difficulty: str
    topic: str


def generate_prompt(data):
    return f"""
You are a school teacher creating a printable worksheet.

Generate a worksheet using the EXACT format below.
Do NOT add explanations, answers, emojis, markdown symbols, or extra text.

SUBJECT: {data.subject}
CLASS: {data.classLevel}
DIFFICULTY: {data.difficulty}
TOPIC: {data.topic}

============================

SECTION A – MCQs (5 Questions)

1. Question text
a) Option
b) Option
c) Option
d) Option

2. Question text
a) Option
b) Option
c) Option
d) Option

(continue till 5 questions)

============================

SECTION B – Fill in the Blanks (5 Questions)

1. _______________________________
2. _______________________________
3. _______________________________
4. _______________________________
5. _______________________________

============================

SECTION C – Short Answer Questions (5 Questions)

1. ______________________________________
2. ______________________________________
3. ______________________________________
4. ______________________________________
5. ______________________________________

============================

SECTION D – Match the Pairs (5 Questions)

Column A            Column B
1. _____            a. _____
2. _____            b. _____
3. _____            c. _____
4. _____            d. _____
5. _____            e. _____

============================

SECTION E – Long Answer Questions (2 Questions)

1. ______________________________________
   ______________________________________
   ______________________________________
2. ______________________________________
   ______________________________________
   ______________________________________

============================

Rules:
- Language must match Grade {data.classLevel} level.
- Keep questions strictly related to "{data.topic}".
- Follow school syllabus style.
- Do NOT include answers.
- Do NOT include explanations.
- Output ONLY the worksheet content.
"""


@router.post("/generate")
def generate(data: WorksheetRequest):

    prompt = generate_prompt(data)

    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {PERPLEXITY_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "sonar-pro",
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
    )

    result = response.json()

    if "choices" not in result:
        return {"error": result}

    worksheet = result["choices"][0]["message"]["content"]

    # Supabase insert (optional)
    if SUPABASE_URL and SUPABASE_KEY:
        payload = {
            "subject": data.subject,
            "class_level": data.classLevel,
            "difficulty": data.difficulty,
            "topic": data.topic,
            "content": worksheet,
            "created_at": datetime.utcnow().isoformat()
        }

        table_candidates = ["worksheet", "worksheets", "Worksheet", "Worksheets"]

        last_error = None
        for table_name in table_candidates:
            try:
                url = f"{SUPABASE_URL}/rest/v1/{table_name}"
                resp = requests.post(
                    url,
                    json=payload,
                    headers={
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Prefer": "return=representation"
                    },
                    timeout=10
                )

                if resp.status_code in (200, 201):
                    try:
                        inserted = resp.json()
                    except Exception:
                        inserted = resp.text
                    return {
                        "worksheet": worksheet,
                        "supabase": {
                            "inserted": True,
                            "table": table_name,
                            "response": inserted
                        }
                    }

                try:
                    last_error = {"status": resp.status_code, "body": resp.json()}
                except Exception:
                    last_error = {"status": resp.status_code, "body": resp.text}

            except Exception as e:
                last_error = {"exception": str(e)}

        return {"worksheet": worksheet, "supabase_error": last_error}

    return {"worksheet": worksheet}


@router.post("/download")
def download(data: dict):

    worksheet = data["worksheet"]
    filename = f"worksheet_{uuid.uuid4().hex}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(worksheet)

    return FileResponse(filename, media_type="text/plain", filename="worksheet.txt")
