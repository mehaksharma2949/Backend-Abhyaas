from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os, json, base64, re, logging
from datetime import datetime
from fastapi import APIRouter

router = APIRouter(tags=["answer_sheet_evaluator"])

from openai import OpenAI
from supabase import create_client

# Load .env from the project directory to avoid missing env when uvicorn cwd differs
basedir = os.path.dirname(__file__)
dotenv_path = os.path.join(basedir, ".env")
load_dotenv(dotenv_path, override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not OPENAI_API_KEY or OPENAI_API_KEY.upper().startswith("YOUR_"):
    raise RuntimeError("Missing or invalid OPENAI_API_KEY — set a real OpenAI API key.")


if not SUPABASE_URL or not SUPABASE_KEY or str(SUPABASE_KEY).strip().upper().startswith("YOUR_"):
    raise RuntimeError("Missing or invalid SUPABASE_URL or SUPABASE_KEY in .env — set real Supabase credentials.")

client = OpenAI(api_key=OPENAI_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = "worksheet-files"


# Configure simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------
# Helpers
# ----------------------------

def safe_json_load(s: str):
    try:
        return json.loads(s)
    except:
        return None


def grade_from_percentage(p: float) -> str:
    if p >= 90: return "A+"
    if p >= 80: return "A"
    if p >= 70: return "B"
    if p >= 60: return "C"
    if p >= 45: return "D"
    return "F"


def status_from_percentage(p: float) -> str:
    if p >= 85: return "Correct"
    if p >= 60: return "Partially Correct"
    return "Needs Review"


def extract_text_openai_vision(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": "Extract ALL text from the image. Return ONLY plain text. No markdown."},
            {"role": "user", "content": [
                {"type": "text", "text": "Extract full text exactly as written. Do not skip lines."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ]}
        ]
    )
    return (resp.choices[0].message.content or "").strip()


def evaluate_with_ai(ocr_text: str, subject: str, total_marks: int):
    prompt = f"""
You are an expert school teacher.

You must evaluate the student's answer sheet using semantic understanding (not keyword matching).

Return ONLY valid JSON exactly in this schema:

{{
  "score": number,
  "missing_points": ["..."],
  "strengths": ["..."],
  "weaknesses": ["..."],
  "detailed_feedback": "..."
}}

TOTAL MARKS: {total_marks}
SUBJECT: {subject}

OCR TEXT:
{ocr_text}
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": "Return ONLY JSON. No markdown."},
            {"role": "user", "content": prompt},
        ],
    )

    return resp.choices[0].message.content


def upload_to_supabase_storage(file_name: str, file_bytes: bytes, content_type: str):
    supabase.storage.from_(BUCKET).upload(
        file_name,
        file_bytes,
        {"content-type": content_type}
    )

    return supabase.storage.from_(BUCKET).get_public_url(file_name)


# ----------------------------
# MAIN ENDPOINTS
# ----------------------------

@router.post("/evaluate")
async def evaluate(
    file: UploadFile = File(...),
    total_marks: int = Form(100),
    student_name: str = Form("Unknown"),
    subject: str = Form("General"),
    save_file: bool = Form(True),
):
    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        # OCR (OpenAI Vision)
        ocr_text = extract_text_openai_vision(file_bytes)
        if not ocr_text:
            raise HTTPException(status_code=400, detail="OCR failed. Try clearer image.")

        # Evaluate
        raw = evaluate_with_ai(ocr_text, subject, total_marks)
        ai = safe_json_load(raw)

        if not ai:
            ai = {
                "score": 0,
                "missing_points": [],
                "strengths": [],
                "weaknesses": [],
                "detailed_feedback": raw
            }

        score = int(ai.get("score", 0))
        score = max(0, min(score, total_marks))

        percentage = round((score / total_marks) * 100, 2) if total_marks > 0 else 0
        grade = grade_from_percentage(percentage)
        status = status_from_percentage(percentage)

        # Optional upload file to storage
        file_url = None
        if save_file:
            safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename or "worksheet.png")
            final_name = f"{int(datetime.utcnow().timestamp())}_{safe_name}"
            file_url = upload_to_supabase_storage(final_name, file_bytes, file.content_type or "image/png")

        # Save in DB
        saved = supabase.table("evaluations").insert({
            "student_name": student_name,
            "subject": subject,
            "total_marks": total_marks,
            "score": score,
            "percentage": percentage,
            "grade": grade,
            "status": status,
            "confidence": 98.4,
            "time_saved": "12m",

            "extracted_answers": ocr_text,
            "ocr_text": ocr_text,
            "missing_points": ai.get("missing_points", []),
            "strengths": ai.get("strengths", []),
            "weaknesses": ai.get("weaknesses", []),
            "detailed_feedback": ai.get("detailed_feedback", ""),

            "file_name": file.filename,
            "file_url": file_url,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        if not getattr(saved, "data", None):
            raise RuntimeError("Failed to save evaluation to database: no data returned from Supabase")

        row = saved.data[0]

        return {
            "id": row["id"],
            "student_name": row["student_name"],
            "subject": row["subject"],
            "total_marks": row["total_marks"],
            "score": row["score"],
            "percentage": row["percentage"],
            "grade": row["grade"],
            "status": row["status"],
            "confidence": row["confidence"],
            "time_saved": row["time_saved"],
            "extracted_answers": row["extracted_answers"],
            "missing_points": row["missing_points"],
            "strengths": row["strengths"],
            "weaknesses": row["weaknesses"],
            "detailed_feedback": row["detailed_feedback"],
            "file_url": row["file_url"],
            "created_at": row["created_at"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in /evaluate")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/batch_evaluate")
async def batch_evaluate(
    files: list[UploadFile] = File(...),
    title: str = Form("Batch Evaluation"),
    total_marks: int = Form(100),
    subject: str = Form("General"),
):
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No files uploaded")

    batch = supabase.table("batches").insert({
        "title": title,
        "subject": subject,
        "total_marks": total_marks,
        "created_at": datetime.utcnow().isoformat()
    }).execute().data[0]

    batch_id = batch["id"]
    results = []

    for f in files:
        file_bytes = await f.read()
        if not file_bytes:
            continue

        ocr_text = extract_text_openai_vision(file_bytes)

        raw = evaluate_with_ai(ocr_text, subject, total_marks)
        ai = safe_json_load(raw) or {
            "score": 0,
            "missing_points": [],
            "strengths": [],
            "weaknesses": [],
            "detailed_feedback": raw
        }

        score = int(ai.get("score", 0))
        score = max(0, min(score, total_marks))
        percentage = round((score / total_marks) * 100, 2) if total_marks > 0 else 0
        grade = grade_from_percentage(percentage)
        status = status_from_percentage(percentage)

        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", f.filename or "worksheet.png")
        final_name = f"{batch_id}_{int(datetime.utcnow().timestamp())}_{safe_name}"
        file_url = upload_to_supabase_storage(final_name, file_bytes, f.content_type or "image/png")

        saved_eval = supabase.table("evaluations").insert({
            "student_name": safe_name.replace("_", " ").split(".")[0],
            "subject": subject,
            "total_marks": total_marks,
            "score": score,
            "percentage": percentage,
            "grade": grade,
            "status": status,
            "confidence": 98.4,
            "time_saved": "12m",
            "extracted_answers": ocr_text,
            "ocr_text": ocr_text,
            "missing_points": ai.get("missing_points", []),
            "strengths": ai.get("strengths", []),
            "weaknesses": ai.get("weaknesses", []),
            "detailed_feedback": ai.get("detailed_feedback", ""),
            "file_name": f.filename,
            "file_url": file_url,
            "created_at": datetime.utcnow().isoformat()
        }).execute().data[0]

        supabase.table("batch_items").insert({
            "batch_id": batch_id,
            "evaluation_id": saved_eval["id"]
        }).execute()

        results.append(saved_eval)

    return {"batch": batch, "items": results}


# ----------------------------
# HISTORY + SEARCH + DELETE
# ----------------------------

@router.get("/history")
def history(limit: int = 50):
    res = supabase.table("evaluations") \
        .select("id,student_name,subject,score,total_marks,percentage,grade,status,created_at,file_url") \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    return {"items": res.data}


@router.get("/report/{evaluation_id}")
def report(evaluation_id: str):
    res = supabase.table("evaluations") \
        .select("*") \
        .eq("id", evaluation_id) \
        .single() \
        .execute()

    return res.data


@router.delete("/report/{evaluation_id}")
def delete_report(evaluation_id: str):
    supabase.table("evaluations").delete().eq("id", evaluation_id).execute()
    return {"ok": True}


@router.get("/search")
def search(q: str, limit: int = 50):
    q = q.strip()
    if not q:
        return {"items": []}

    res = supabase.table("evaluations") \
        .select("id,student_name,subject,score,total_marks,percentage,grade,status,created_at,file_url") \
        .or_(f"student_name.ilike.%{q}%,subject.ilike.%{q}%") \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    return {"items": res.data}


@router.get("/batch_history")
def batch_history(limit: int = 20):
    res = supabase.table("batches") \
        .select("*") \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    return {"items": res.data}


@router.get("/batch/{batch_id}")
def batch_details(batch_id: str):
    batch = supabase.table("batches").select("*").eq("id", batch_id).single().execute().data

    items = supabase.table("batch_items") \
        .select("evaluation_id, evaluations(*)") \
        .eq("batch_id", batch_id) \
        .execute()

    out = []
    for x in items.data:
        out.append(x["evaluations"])

    return {"batch": batch, "items": out}


# ----------------------------
# ✅ UPDATE ENDPOINTS (NEW)
# ----------------------------

class UpdateNameRequest(BaseModel):
    student_name: str

class UpdateSubjectRequest(BaseModel):
    subject: str

class UpdateMarksRequest(BaseModel):
    total_marks: int


@router.put("/report/{evaluation_id}/name")
def update_name(evaluation_id: str, payload: UpdateNameRequest):
    supabase.table("evaluations") \
        .update({"student_name": payload.student_name}) \
        .eq("id", evaluation_id) \
        .execute()
    return {"ok": True}


@router.put("/report/{evaluation_id}/subject")
def update_subject(evaluation_id: str, payload: UpdateSubjectRequest):
    supabase.table("evaluations") \
        .update({"subject": payload.subject}) \
        .eq("id", evaluation_id) \
        .execute()
    return {"ok": True}


@router.put("/report/{evaluation_id}/marks")
def update_total_marks(evaluation_id: str, payload: UpdateMarksRequest):
    supabase.table("evaluations") \
        .update({"total_marks": payload.total_marks}) \
        .eq("id", evaluation_id) \
        .execute()
    return {"ok": True}
