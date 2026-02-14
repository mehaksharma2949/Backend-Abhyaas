import os
import json
import subprocess
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, APIRouter
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont

from supabase import create_client, Client
from groq import Groq

# ✅ Edge TTS (FREE)
import edge_tts
import asyncio


router = APIRouter(tags=["Video"])

# =========================
# CONFIG
# =========================
load_dotenv()

# --- GROQ ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- SUPABASE ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY missing in env")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY missing in env")

groq_client = Groq(api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# =========================
# PATHS
# =========================
APP_DIR = Path(__file__).resolve().parents[1]  # backend/app
ASSETS_DIR = APP_DIR / "assets"
OUT_DIR = APP_DIR / "outputs"

AUDIO_DIR = OUT_DIR / "audio"
FRAMES_DIR = OUT_DIR / "frames"
VIDEOS_DIR = OUT_DIR / "videos"

for d in [AUDIO_DIR, FRAMES_DIR, VIDEOS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# =========================
# LOAD TEACHER ASSETS
# =========================
def load_teacher_asset(filename: str):
    p = ASSETS_DIR / filename
    if not p.exists():
        raise HTTPException(status_code=500, detail=f"Missing teacher asset: {p}")
    return Image.open(p).convert("RGBA")

TEACHER_IDLE = load_teacher_asset("teacher_idle.png.png")
TEACHER_POINT = load_teacher_asset("teacher_point.png.png")
TEACHER_HAPPY = load_teacher_asset("teacher_happy.png.png")
TEACHER_THINK = load_teacher_asset("teacher_think.png.png")

# =========================
# REQUEST MODEL
# =========================
class VideoRequest(BaseModel):
    topic: str
    grade: int = 5
    language: str = "hinglish"

# =========================
# 1) LESSON GENERATOR (GROQ)
# =========================
def generate_lesson(topic: str, grade: int, language: str):
    prompt = f"""
You are an expert math teacher for Indian kids.

Make a VIDEO LESSON.

Topic: {topic}
Grade: {grade}
Language: {language}

Return STRICT JSON only:

{{
  "title": "...",
  "scenes": [
    {{
      "id": 1,
      "narration": "...",
      "subtitle": "...",
      "example": {{
        "question": "...",
        "steps": ["...", "...", "...", "..."]
      }}
    }}
  ]
}}

Rules:
- Exactly 14 scenes.
- Each narration should be 2-3 lines only.
- Every scene must teach ONE thing only.
- Include at least 3 solved questions total.
- NCERT style language.
- Teacher tone.
- No markdown.
"""

    resp = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Return strict JSON only. No markdown."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.55,
    )

    text = resp.choices[0].message.content
    if not text:
        raise HTTPException(status_code=500, detail="Groq returned empty lesson JSON")

    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(text)

        if "scenes" not in data or len(data["scenes"]) != 14:
            raise Exception("Lesson JSON does not contain exactly 14 scenes")

        return data

    except Exception:
        raise HTTPException(status_code=500, detail=f"Invalid JSON from Groq:\n{text[:800]}")

# =========================
# 2) EDGE TTS (FREE)
# =========================
async def edge_tts_generate(text: str, out_path: Path):
    # Best voices:
    # - en-IN-NeerjaNeural (female)
    # - en-IN-PrabhatNeural (male)
    voice = "en-IN-NeerjaNeural"

    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(out_path))

def generate_tts_audio(text: str, out_path: Path):
    asyncio.run(edge_tts_generate(text, out_path))

# =========================
# 3) AUDIO DURATION
# =========================
def get_audio_duration_seconds(audio_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return 60.0

    try:
        return float(result.stdout.strip())
    except:
        return 60.0

# =========================
# 4) FRAME RENDER (CARTOON TEACHER)
# =========================
def render_scene_frame(scene, frame_path: Path, t: float, scene_duration: float, scene_index: int):
    W, H = 1280, 720
    bg = Image.new("RGBA", (W, H), (18, 18, 28, 255))
    draw = ImageDraw.Draw(bg)

    # glow
    draw.ellipse((-250, -200, 550, 400), fill=(120, 80, 255, 55))
    draw.ellipse((850, 450, 1600, 1000), fill=(50, 255, 140, 45))

    # teacher pose based on scene index
    if scene_index % 4 == 0:
        teacher = TEACHER_IDLE
    elif scene_index % 4 == 1:
        teacher = TEACHER_POINT
    elif scene_index % 4 == 2:
        teacher = TEACHER_THINK
    else:
        teacher = TEACHER_HAPPY

    # resize teacher
    teacher = teacher.resize((360, 520))

    # paste teacher left
    bg.alpha_composite(teacher, (40, 160))

    # board
    board_x, board_y = 430, 70
    board_w, board_h = 820, 580

    draw.rounded_rectangle(
        (board_x, board_y, board_x + board_w, board_y + board_h),
        radius=30,
        fill=(10, 10, 18, 210),
        outline=(255, 255, 255, 70),
        width=2
    )

    # fonts
    try:
        font_big = ImageFont.truetype("arial.ttf", 44)
        font_small = ImageFont.truetype("arial.ttf", 30)
        font_tiny = ImageFont.truetype("arial.ttf", 26)
    except:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()

    subtitle = scene.get("subtitle", "")
    draw.text((board_x + 30, board_y + 25), subtitle, font=font_big, fill=(255, 255, 255, 240))

    ex = scene.get("example", {})
    q = ex.get("question", "")
    steps = ex.get("steps", [])

    # step reveal
    reveal_speed = 1.1
    lines_to_show = int(t / reveal_speed)
    lines_to_show = max(0, min(lines_to_show, len(steps)))

    y = board_y + 110

    if t > 0.4:
        draw.text((board_x + 30, y), f"Q: {q}", font=font_small, fill=(255, 255, 255, 230))
    y += 60

    for i in range(lines_to_show):
        st = steps[i]
        draw.text((board_x + 40, y), f"{i+1}. {st}", font=font_tiny, fill=(190, 230, 255, 240))
        y += 44

    # narration bubble (top-left)
    bubble = scene.get("narration", "")
    bx, by = 40, 40
    bw, bh = 360, 110

    draw.rounded_rectangle(
        (bx, by, bx + bw, by + bh),
        radius=20,
        fill=(0, 0, 0, 150),
        outline=(255, 255, 255, 40),
        width=2
    )

    chars_to_show = int((t / scene_duration) * len(bubble))
    draw.text((bx + 16, by + 16), bubble[:chars_to_show], font=font_tiny, fill=(255, 255, 255, 240))

    bg.convert("RGB").save(frame_path, "PNG")

# =========================
# 5) CREATE FRAMES
# =========================
def create_frames_for_video(video_id: str, lesson: dict, final_audio_path: Path):
    frames_folder = FRAMES_DIR / video_id
    frames_folder.mkdir(parents=True, exist_ok=True)

    fps = 12
    frame_num = 1

    total_dur = get_audio_duration_seconds(final_audio_path)
    scenes_count = len(lesson["scenes"])
    scene_dur = max(6.0, total_dur / scenes_count)

    for scene_index, scene in enumerate(lesson["scenes"]):
        frames_per_scene = int(scene_dur * fps)

        for f in range(frames_per_scene):
            t = f / fps
            frame_path = frames_folder / f"frame_{frame_num:05d}.png"
            render_scene_frame(scene, frame_path, t, scene_dur, scene_index)
            frame_num += 1

    return frames_folder, fps

# =========================
# 6) FFMPEG MP4
# =========================
def render_video_ffmpeg(frames_folder: Path, fps: int, audio_path: Path, out_mp4: Path):
    cmd = [
        "ffmpeg",
        "-y",
        "-r", str(fps),
        "-i", str(frames_folder / "frame_%05d.png"),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(out_mp4)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg failed:\n{result.stdout}\n{result.stderr}"
        )

# =========================
# 7) UPLOAD TO SUPABASE STORAGE
# =========================
def upload_file(bucket: str, file_path: Path, dest_path: str, content_type: str):
    data = file_path.read_bytes()

    supabase.storage.from_(bucket).upload(
        dest_path,
        data,
        file_options={"content-type": content_type}
    )

    return supabase.storage.from_(bucket).get_public_url(dest_path)

# =========================
# API: CREATE VIDEO
# =========================
@router.post("/render-video")
def render_video(req: VideoRequest):
    if req.grade < 3 or req.grade > 8:
        raise HTTPException(status_code=400, detail="Grade must be 3–8")

    row = supabase.table("videos").insert({
        "topic": req.topic,
        "grade": req.grade,
        "language": req.language,
        "status": "processing"
    }).execute()

    video_id = str(row.data[0]["id"])

    try:
        # 1) lesson json from Groq
        lesson = generate_lesson(req.topic, req.grade, req.language)

        supabase.table("videos").update({
            "title": lesson.get("title"),
            "lesson_json": lesson
        }).eq("id", video_id).execute()

        # 2) single narration -> single TTS call
        final_audio = AUDIO_DIR / f"{video_id}.mp3"

        full_narration = "\n\n".join([
            f"Scene {i+1}. {s.get('narration','')}"
            for i, s in enumerate(lesson["scenes"])
        ])

        generate_tts_audio(full_narration, final_audio)

        # 3) frames
        frames_folder, fps = create_frames_for_video(video_id, lesson, final_audio)

        # 4) mp4
        out_mp4 = VIDEOS_DIR / f"{video_id}.mp4"
        render_video_ffmpeg(frames_folder, fps, final_audio, out_mp4)

        # 5) upload
        video_url = upload_file("videos", out_mp4, f"{video_id}.mp4", "video/mp4")
        audio_url = upload_file("videos", final_audio, f"{video_id}.mp3", "audio/mpeg")

        supabase.table("videos").update({
            "status": "done",
            "video_url": video_url,
            "audio_url": audio_url
        }).eq("id", video_id).execute()

        return {
            "id": video_id,
            "status": "done",
            "title": lesson.get("title"),
            "video_url": video_url
        }

    except Exception as e:
        traceback.print_exc()

        supabase.table("videos").update({
            "status": "failed",
            "error": str(e)
        }).eq("id", video_id).execute()

        raise HTTPException(status_code=500, detail=str(e))
