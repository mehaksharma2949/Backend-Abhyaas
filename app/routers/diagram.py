from fastapi import HTTPException, APIRouter

from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter(tags=["Diagram"])

import os
import re
import base64
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client


# =========================
# FORCE LOAD .env (FIXED)
# =========================
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# =========================
# ENV + CLIENTS
# =========================
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("ENV PATH USED:", ENV_PATH)
print("OPENAI KEY LOADED:", "YES" if OPENAI_KEY and OPENAI_KEY.startswith("sk-") else "NO")

if not OPENAI_KEY:
    raise RuntimeError("OPENAI_API_KEY missing in .env")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY missing in .env")

client = OpenAI(api_key=OPENAI_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Supabase storage bucket name
BUCKET = "diagram-png"


# =========================
# FASTAPI APP
# =========================


# =========================
# MODELS
# =========================
class DiagramRequest(BaseModel):
    prompt: str
    type: str  # board, mindmap, flowchart, orgchart, sequence, er, hierarchy


class UploadPNGRequest(BaseModel):
    base64_png: str  # data:image/png;base64,...
    prompt: str
    type: str


# =========================
# HELPERS
# =========================
def extract_svg(text: str) -> str:
    if not text:
        return ""
    match = re.search(r"<svg[\s\S]*?</svg>", text, re.IGNORECASE)
    return match.group(0).strip() if match else ""


def clean_type(dtype: str) -> str:
    return (dtype or "").strip().lower()


# =========================
# ROUTES
# =========================
@router.get("/", response_class=HTMLResponse)
def serve_board():
    html_path = BASE_DIR / "board.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="board.html not found")

    return html_path.read_text(encoding="utf-8")


@router.post("/generate")
def generate_diagram(data: DiagramRequest):
    prompt = (data.prompt or "").strip()
    dtype = clean_type(data.type)

    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    allowed = ["board", "mindmap", "flowchart", "orgchart", "sequence", "er", "hierarchy"]
    if dtype not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid type. Allowed: {allowed}")

    # ---------- SYSTEM PROMPT ----------
    system_prompt = f"""
Return ONLY raw SVG.
No markdown.
No triple backticks.
No explanation.
No text outside <svg>.

Diagram Type: {dtype}

Global Rules:
- SVG must be width=900 height=550 viewBox="0 0 900 550"
- Use white background (#ffffff)
- Use black strokes (#111)
- Use neat spacing and alignment
- Use consistent font size 14-18px
- Use <defs> arrow marker for arrows
- Make it clean and readable like a teacher board
"""

    if dtype == "board":
        system_prompt += """
Board Diagram Rules:
- Use slightly thicker strokes (2.5 to 3)
- Use simple classroom symbols (battery, bulb, switch, wires)
- Add clear labels
- Add current direction arrows if relevant
- Avoid complex decorations
"""

    if dtype == "mindmap":
        system_prompt += """
Mindmap Rules:
- Put topic in center node
- Use 4-7 main branches
- Each branch has 2-4 sub points
- Use rounded boxes or circles
"""

    if dtype == "flowchart":
        system_prompt += """
Flowchart Rules:
- Use start/end, process boxes, decision diamonds
- Use arrows for flow
- Keep it simple and structured
"""

    if dtype == "orgchart":
        system_prompt += """
Org Chart Rules:
- Use hierarchy layout top to bottom
- Use connecting lines
- Use clean rectangles for roles
"""

    if dtype == "sequence":
        system_prompt += """
Sequence Map Rules:
- Show steps in order (1,2,3...)
- Use arrows between steps
- Keep each step short
"""

    if dtype == "er":
        system_prompt += """
ER Diagram Rules:
- Entities as boxes
- Attributes as smaller text inside entity
- Relationships with connecting lines
"""

    if dtype == "hierarchy":
        system_prompt += """
Hierarchy Rules:
- Tree structure
- Root at top, children below
- Use connectors clearly
"""

    # ---------- USER PROMPT ----------
    user_prompt = f"""
Create a classroom board style {dtype} diagram for this topic:

TOPIC: {prompt}

Return only SVG.
"""

    # ---------- OPENAI CALL ----------
    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI error: {str(e)}")

    raw = completion.choices[0].message.content or ""
    svg = extract_svg(raw)

    if not svg:
        raise HTTPException(status_code=500, detail="No valid SVG returned from OpenAI")

    # ---------- SAVE TO SUPABASE ----------
    try:
        supabase.table("diagrams").insert({
            "prompt": prompt,
            "diagram_type": dtype,
            "svg": svg,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase insert error: {str(e)}")

    return {"svg": svg, "type": dtype}


@router.post("/upload_png")
def upload_png(data: UploadPNGRequest):
    dtype = clean_type(data.type)

    if not data.base64_png.startswith("data:image/png;base64,"):
        raise HTTPException(status_code=400, detail="Invalid base64 png format")

    try:
        b64 = data.base64_png.split(",")[1]
        png_bytes = base64.b64decode(b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Base64 decode failed")

    filename = f"{dtype}_{int(datetime.utcnow().timestamp())}.png"

    try:
        supabase.storage.from_(BUCKET).upload(
            filename,
            png_bytes,
            {"content-type": "image/png"}
        )
        public_url = supabase.storage.from_(BUCKET).get_public_url(filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {str(e)}")

    # Save URL in DB
    try:
        supabase.table("diagram_exports").insert({
            "prompt": data.prompt,
            "diagram_type": dtype,
            "png_url": public_url,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {str(e)}")

    return {"png_url": public_url}


@router.get("/history")
def history(limit: int = 15):
    try:
        res = supabase.table("diagrams") \
            .select("id,prompt,diagram_type,created_at") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        return {"items": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagram/{diagram_id}")
def get_diagram(diagram_id: str):
    try:
        res = supabase.table("diagrams") \
            .select("id,prompt,diagram_type,created_at,svg") \
            .eq("id", diagram_id) \
            .single() \
            .execute()

        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/diagram/{diagram_id}")
def delete_diagram(diagram_id: str):
    try:
        supabase.table("diagrams").delete().eq("id", diagram_id).execute()
        return {"success": True, "deleted_id": diagram_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
def search_diagrams(q: str, limit: int = 20):
    try:
        res = supabase.table("diagrams") \
            .select("id,prompt,diagram_type,created_at") \
            .ilike("prompt", f"%{q}%") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()

        return {"items": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
