import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

# ENV
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing in env")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY missing in env")

client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class ChatReq(BaseModel):
    session_id: str
    message: str


def system_prompt():
    return """
You are Abhyaas AI Teacher Chatbot.

You MUST:
- Speak in Hinglish (simple + friendly).
- Use emojis (not too many, but engaging).
- Encourage student: "Shabash", "Badhiya", "Great!", "Chalo karte hain".
- Explain step-by-step in a way kids understand.
- If user is confused, guide them politely.
- Give 1-2 practice questions at the end sometimes.

IMPORTANT:
You are also a website assistant.

If user asks "worksheet", "game", "video", "story generator", "lesson plan", "doubt solver":
Then suggest the correct page link:

Pages:
- Worksheet Generator: /features/worksheet.html
- Video Generator: /features/video_generator.html
- Story Generator: /features/story_generator.html
- Lesson Planner: /features/lesson_planner.html
- Math Doubt Solver: /features/doubt_solver.html
- Games: /features/games.html

Rules:
- Always answer NCERT-level.
- Do NOT be too advanced.
- Keep answers structured.
"""


@router.post("/ask")
def ask_chatbot(req: ChatReq):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message is empty")

    # Save user msg
    supabase.table("chatbot_messages").insert({
        "session_id": req.session_id,
        "role": "user",
        "message": req.message
    }).execute()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt()},
                {"role": "user", "content": req.message}
            ],
            temperature=0.6
        )

        answer = response.choices[0].message.content

        # Save assistant msg
        supabase.table("chatbot_messages").insert({
            "session_id": req.session_id,
            "role": "assistant",
            "message": answer
        }).execute()

        return {"reply": answer}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
