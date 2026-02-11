import os
import json
import re
import math
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import HTTPException, APIRouter, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter(tags=["Fluency"])

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

# Supabase
from supabase import create_client, Client


# =========================
# CONFIG
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found.")

client = OpenAI(api_key=OPENAI_API_KEY)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_KEY")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    print("✅ Supabase connected")
else:
    print("⚠️ Supabase not configured")




# =========================
# FULL NCERT (Class 3–8)
# =========================
NCERT: Dict[str, Dict[str, List[str]]] = {
    "3": {"EVS": ["Poonam's Day Out"], "English": ["Good Morning"]},
    "4": {"EVS": ["Going to School"], "English": ["Wake Up!"]},
    "5": {"EVS": ["Super Senses"], "English": ["The Lazy Frog"]},
    "6": {"Science": ["Components of Food"], "SST": ["History: What, Where, How and When?"], "English": ["Fair Play"]},
    "7": {"Science": ["Heat"], "SST": ["History: The Mughal Empire"], "English": ["Three Questions"]},
    "8": {"Science": ["Friction"], "SST": ["History: From Trade to Territory"], "English": ["The Tsunami"]},
}

# NOTE:
# Tum chaaho toh is NCERT dict me tumhara full list paste kar sakti ho.
# Fluency checker me chapter matching optional hai.


# =========================
# HELPERS
# =========================
def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("’", "'").replace("–", "-")
    s = re.sub(r"\s+", " ", s)
    return s


def count_words(s: str) -> int:
    s = s.strip()
    if not s:
        return 0
    return len(re.findall(r"\b[\w']+\b", s))


def diff_words(expected: str, spoken: str) -> dict:
    """
    Simple word-level comparison:
    - accuracy %
    - missing words
    - extra words
    - wrong words (approx)
    """

    exp = re.findall(r"\b[\w']+\b", normalize_text(expected))
    spk = re.findall(r"\b[\w']+\b", normalize_text(spoken))

    exp_set = exp[:]  # list
    spk_set = spk[:]

    # Very simple scoring:
    # matched words = intersection count (multiset approx)
    matched = 0
    exp_copy = exp_set[:]
    for w in spk_set:
        if w in exp_copy:
            matched += 1
            exp_copy.remove(w)

    total = max(len(exp_set), 1)
    accuracy = round((matched / total) * 100, 1)

    missing = exp_copy[:]
    extras = [w for w in spk_set if w not in exp_set]

    # Wrong words (approx):
    wrong = []
    for i in range(min(len(exp_set), len(spk_set))):
        if exp_set[i] != spk_set[i]:
            wrong.append({"expected": exp_set[i], "spoken": spk_set[i]})

    return {
        "accuracy": accuracy,
        "matched_words": matched,
        "total_expected_words": len(exp_set),
        "missing_words": missing[:15],
        "extra_words": extras[:15],
        "wrong_words": wrong[:15],
    }


def fluency_label(wpm: float, pauses_hint: int) -> str:
    # Govt school friendly thresholds
    if wpm >= 95 and pauses_hint <= 2:
        return "Excellent"
    if wpm >= 75 and pauses_hint <= 4:
        return "Good"
    if wpm >= 55:
        return "Average"
    return "Needs Practice"


# =========================
# REQUEST MODELS
# =========================
class PassageRequest(BaseModel):
    class_level: str
    language: str = "Hindi"
    subject: str = "Auto"
    chapter: str = ""
    level: str = "Easy"  # Easy / Medium


# =========================
# ROUTES
# =========================
@router.get("/")
def root():
    return {"ok": True, "service": "Abhyaas Reading Fluency Checker"}


@router.post("/api/generate_passage")
def generate_passage(req: PassageRequest):
    if req.class_level not in ["3", "4", "5", "6", "7", "8"]:
        raise HTTPException(status_code=400, detail="Invalid class")

    prompt = f"""
You are an Indian government school teacher.

TASK:
Create ONE reading passage for fluency practice.

RULES:
- Class: {req.class_level}
- Language: {req.language}
- Level: {req.level}
- Keep it NCERT aligned.
- If chapter is provided, align to that chapter.
- Passage should be 60 to 90 words (class 3-5) OR 90 to 140 words (class 6-8).
- Use very simple words.
- Avoid hard names.
- Make it interesting.

OUTPUT JSON ONLY:
{{
  "title": "...",
  "passage": "...",
  "focus_words": ["...", "...", "...", "...", "..."],
  "tip": "..."
}}
""".strip()

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        raw = resp.choices[0].message.content.strip()
        data = json.loads(raw) if raw.startswith("{") else json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group(0))

        return {"ok": True, "data": data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Passage generation failed: {str(e)}")


@router.post("/api/check_fluency")
async def check_fluency(
    expected_text: str = Form(...),
    class_level: str = Form(...),
    language: str = Form("Hindi"),
    duration_seconds: float = Form(...),
    audio: UploadFile = File(...)
):
    """
    Frontend sends:
    - expected_text (passage shown)
    - duration_seconds (recorded length)
    - audio file (webm)
    """

    if not expected_text.strip():
        raise HTTPException(status_code=400, detail="expected_text missing")

    if duration_seconds <= 0:
        raise HTTPException(status_code=400, detail="duration_seconds invalid")

    # Read audio bytes
    audio_bytes = await audio.read()
    if len(audio_bytes) < 2000:
        raise HTTPException(status_code=400, detail="Audio too small. Please record again.")

    # =========================
    # 1) Speech to Text (Whisper)
    # =========================
    try:
        stt = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=("audio.webm", audio_bytes)
        )
        spoken_text = stt.text.strip()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech to text failed: {str(e)}")

    # =========================
    # 2) Compute metrics
    # =========================
    expected_words = count_words(expected_text)
    spoken_words = count_words(spoken_text)

    minutes = duration_seconds / 60.0
    wpm = round(spoken_words / max(minutes, 0.01), 1)

    # pause hint: if wpm too low => more pauses
    pauses_hint = 6 if wpm < 45 else 4 if wpm < 60 else 2 if wpm < 85 else 1

    diff = diff_words(expected_text, spoken_text)
    fluency = fluency_label(wpm, pauses_hint)

    # Simple feedback
    feedback = []
    if diff["accuracy"] < 85:
        feedback.append("Accuracy thodi kam hai. Dheere aur saaf padho.")
    if wpm < 55:
        feedback.append("Speed thodi slow hai. Roz 1 minute reading practice karo.")
    if diff["missing_words"]:
        feedback.append("Kuch words chhoot rahe hain. Line by line padho.")
    if not feedback:
        feedback.append("Bahut badhiya! Aapki reading strong hai.")

    # =========================
    # 3) Save to Supabase
    # =========================
    saved_id = None
    if supabase is not None:
        try:
            payload = {
                "class_level": class_level,
                "language": language,
                "expected_text": expected_text,
                "spoken_text": spoken_text,
                "duration_seconds": duration_seconds,
                "wpm": wpm,
                "accuracy": diff["accuracy"],
                "fluency": fluency,
                "report_json": {
                    "diff": diff,
                    "feedback": feedback
                }
            }
            res = supabase.table("fluency_reports").insert(payload).execute()
            if res.data and len(res.data) > 0:
                saved_id = res.data[0].get("id")
        except Exception as e:
            print("Supabase save failed:", str(e))

    return JSONResponse({
        "ok": True,
        "saved_id": saved_id,
        "expected_text": expected_text,
        "spoken_text": spoken_text,
        "metrics": {
            "accuracy": diff["accuracy"],
            "wpm": wpm,
            "fluency": fluency,
            "expected_words": expected_words,
            "spoken_words": spoken_words,
            "duration_seconds": duration_seconds
        },
        "mistakes": {
            "missing_words": diff["missing_words"],
            "extra_words": diff["extra_words"],
            "wrong_words": diff["wrong_words"]
        },
        "feedback": feedback
    })


@router.get("/api/fluency_history")
def fluency_history():
    if supabase is None:
        raise HTTPException(status_code=400, detail="Supabase not configured")

    try:
        res = (
            supabase
            .table("fluency_reports")
            .select("id, created_at, class_level, language, wpm, accuracy, fluency")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return {"ok": True, "items": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History fetch failed: {str(e)}")
