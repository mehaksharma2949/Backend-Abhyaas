import os
import uuid
import traceback
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from openai import OpenAI
from PIL import Image
import pytesseract

from supabase import create_client, Client


router = APIRouter(tags=["Doubt Solver"])

# =========================
# CONFIG
# =========================
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not OPENAI_KEY:
    raise RuntimeError("OPENAI_API_KEY missing in env")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY missing in env")

client = OpenAI(api_key=OPENAI_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# LOCAL TEMP UPLOADS
# =========================
BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR / "outputs" / "doubts"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# HELPERS
# =========================
def extract_text_from_image(image_path: Path) -> str:
    try:
        img = Image.open(image_path).convert("RGB")
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception:
        return ""


def upload_to_supabase_storage(local_path: Path, file_name: str) -> str:
    data = local_path.read_bytes()

    supabase.storage.from_("doubt-images").upload(
        file_name,
        data,
        file_options={"content-type": "image/png"}
    )

    return supabase.storage.from_("doubt-images").get_public_url(file_name)


def build_prompt(question: str, grade: str) -> str:
    return f"""
You are a friendly Indian math teacher.

Solve the given math doubt for Grade/Class {grade} level.

Rules:
- Explain step-by-step
- Do NOT use markdown
- Keep language simple
- Final answer must be clearly written

Question:
{question}

Output Format:

QUESTION:
...

STEP BY STEP SOLUTION:
1)
2)
3)

FINAL ANSWER:
...

EXTRA TIP:
...
"""


# =========================
# API: SOLVE DOUBT
# =========================
@router.post("/solve")
async def solve_doubt(
    grade: str = Form("5"),
    question: str = Form(""),
    image: UploadFile = File(None),
):
    row = supabase.table("doubts").insert({
        "grade": grade,
        "question": question,
        "status": "processing"
    }).execute()

    doubt_id = str(row.data[0]["id"])

    try:
        final_question = question.strip()
        extracted_text = ""
        image_url = None

        # -----------------------
        # IMAGE -> OCR + UPLOAD
        # -----------------------
        if image:
            file_id = uuid.uuid4().hex
            img_path = UPLOAD_DIR / f"{file_id}.png"

            content = await image.read()
            img_path.write_bytes(content)

            extracted_text = extract_text_from_image(img_path)

            # upload to supabase storage
            image_url = upload_to_supabase_storage(img_path, f"{doubt_id}.png")

            if extracted_text:
                final_question = (final_question + "\n\n" + extracted_text).strip()

        if not final_question:
            raise HTTPException(status_code=400, detail="Please type a question or upload an image.")

        # update question after OCR
        supabase.table("doubts").update({
            "question": final_question,
            "extracted_text": extracted_text,
            "image_url": image_url
        }).eq("id", doubt_id).execute()

        # -----------------------
        # OPENAI SOLVE
        # -----------------------
        prompt = build_prompt(final_question, grade)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You solve math doubts step by step."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )

        solution = response.choices[0].message.content

        # save final solution
        supabase.table("doubts").update({
            "solution": solution,
            "status": "done"
        }).eq("id", doubt_id).execute()

        return {
            "id": doubt_id,
            "status": "done",
            "question": final_question,
            "solution": solution,
            "image_url": image_url
        }

    except Exception as e:
        traceback.print_exc()

        supabase.table("doubts").update({
            "status": "failed",
            "error": str(e)
        }).eq("id", doubt_id).execute()

        raise HTTPException(status_code=500, detail=str(e))
