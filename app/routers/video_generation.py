import os
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from fastapi import HTTPException, APIRouter
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI
from supabase import create_client, Client

router = APIRouter(tags=["Video"])

# =========================
# CONFIG
# =========================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing in .env")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_KEY missing in .env")

client = OpenAI(api_key=OPENAI_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# =========================
# PATHS (IMPORTANT)
# =========================
APP_DIR = Path(__file__).resolve().parents[1]   # backend/app
ASSETS_DIR = APP_DIR / "assets"
OUT_DIR = APP_DIR / "outputs"

LESSONS_DIR = OUT_DIR / "lessons"
AUDIO_DIR = OUT_DIR / "audio"
FRAMES_DIR = OUT_DIR / "frames"
VIDEOS_DIR = OUT_DIR / "videos"

for d in [LESSONS_DIR, AUDIO_DIR, FRAMES_DIR, VIDEOS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# =========================
# REQUEST MODEL
# =========================
class VideoRequest(BaseModel):
    topic: str
    grade: int = 5
    language: str = "hinglish"

# =========================
# 1) LESSON GENERATOR (14 scenes)
# =========================
def generate_lesson(topic: str, grade: int, language: str):
    prompt = f"""
You are an expert math teacher for Indian kids.

Make a long VIDEO LESSON.

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
- Each narration should be 2-3 lines.
- Every scene must teach ONE thing only.
- Include at least 3 solved questions total.
- Use NCERT style language.
- Must feel like teacher is teaching.
- No markdown.
"""

    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "Return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.55,
    )

    text = resp.choices[0].message.content.strip()
    return json.loads(text)

# =========================
# 2) TTS AUDIO
# =========================
def generate_tts_audio(text: str, out_path: Path):
    audio = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice="alloy",
        input=text
    )
    out_path.write_bytes(audio.read())

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
        return 6.0
    try:
        return float(result.stdout.strip())
    except:
        return 6.0

# =========================
# 4) MERGE AUDIOS
# =========================
def merge_scene_audios(scene_audio_paths, out_audio: Path):
    list_file = out_audio.parent / f"{out_audio.stem}_list.txt"

    with open(list_file, "w", encoding="utf-8") as f:
        for p in scene_audio_paths:
            f.write(f"file '{p.as_posix()}'\n")

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(out_audio)
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Audio merge failed:\n{result.stdout}\n{result.stderr}"
        )

# =========================
# 5) LOAD ASSET
# =========================
def load_asset(name: str):
    path = ASSETS_DIR / name
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Missing asset: {path}")
    return Image.open(path).convert("RGBA")

# =========================
# 6) FRAME RENDER
# =========================
def render_scene_frame(scene, frame_path: Path, scene_index: int, t: float, scene_duration: float):
    W, H = 1280, 720
    bg = Image.new("RGBA", (W, H), (20, 20, 35, 255))
    draw = ImageDraw.Draw(bg)

    # glow
    draw.ellipse((-200, -150, 500, 350), fill=(120, 80, 255, 60))
    draw.ellipse((900, 450, 1500, 1000), fill=(50, 255, 120, 50))



    # board
    board_x, board_y = 420, 90
    board_w, board_h = 820, 520

    draw.rounded_rectangle(
        (board_x, board_y, board_x + board_w, board_y + board_h),
        radius=28,
        fill=(10, 10, 18, 200),
        outline=(255, 255, 255, 60),
        width=2
    )

    # fonts
    try:
        font_big = ImageFont.truetype("arial.ttf", 48)
        font_small = ImageFont.truetype("arial.ttf", 30)
        font_tiny = ImageFont.truetype("arial.ttf", 26)
    except:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()

    subtitle = scene.get("subtitle", "")
    draw.text((board_x + 30, board_y + 20), subtitle, font=font_big, fill=(255, 255, 255, 240))

    ex = scene.get("example", {})
    q = ex.get("question", "")
    steps = ex.get("steps", [])

    # step reveal
    reveal_speed = 1.4
    lines_to_show = int(t / reveal_speed)
    lines_to_show = max(0, min(lines_to_show, len(steps)))

    y = board_y + 100

    if t > 0.5:
        draw.text((board_x + 30, y), f"Q: {q}", font=font_small, fill=(255, 255, 255, 220))
    y += 60

    for i in range(lines_to_show):
        st = steps[i]
        draw.text((board_x + 40, y), f"{i+1}. {st}", font=font_tiny, fill=(200, 230, 255, 230))
        y += 40

    # speech bubble
    bubble = scene.get("narration", "")
    bx, by = 50, 70
    bw, bh = 330, 150

    draw.rounded_rectangle(
        (bx, by, bx + bw, by + bh),
        radius=22,
        fill=(0, 0, 0, 150),
        outline=(255, 255, 255, 40),
        width=2
    )

    chars_to_show = int((t / scene_duration) * len(bubble))
    draw.text((bx + 18, by + 18), bubble[:chars_to_show], font=font_tiny, fill=(255, 255, 255, 240))

    bg.convert("RGB").save(frame_path, "PNG")

# =========================
# 7) CREATE FRAMES
# =========================
def create_frames_for_video(video_id: str, lesson: dict, scene_audio_paths):
    frames_folder = FRAMES_DIR / video_id
    frames_folder.mkdir(parents=True, exist_ok=True)

    fps = 30
    frame_num = 1

    for s_index, scene in enumerate(lesson["scenes"]):
        dur = get_audio_duration_seconds(scene_audio_paths[s_index])

        if dur < 7.0:
            dur = 7.0

        dur += 0.2
        frames_per_scene = int(dur * fps)

        for f in range(frames_per_scene):
            t = f / fps
            frame_path = frames_folder / f"frame_{frame_num:05d}.png"
            render_scene_frame(scene, frame_path, s_index, t, dur)
            frame_num += 1

    return frames_folder

# =========================
# 8) FFMPEG MP4
# =========================
def render_video_ffmpeg(frames_folder: Path, audio_path: Path, out_mp4: Path):
    cmd = [
        "ffmpeg",
        "-y",
        "-r", "30",
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
# 9) UPLOAD TO SUPABASE STORAGE
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
        lesson = generate_lesson(req.topic, req.grade, req.language)

        supabase.table("videos").update({
            "title": lesson.get("title"),
            "lesson_json": lesson
        }).eq("id", video_id).execute()

        scene_audio_paths = []
        for i, s in enumerate(lesson["scenes"]):
            scene_audio = AUDIO_DIR / f"{video_id}_scene{i+1}.mp3"
            generate_tts_audio(s["narration"], scene_audio)
            scene_audio_paths.append(scene_audio)

        final_audio = AUDIO_DIR / f"{video_id}.mp3"
        merge_scene_audios(scene_audio_paths, final_audio)

        frames_folder = create_frames_for_video(video_id, lesson, scene_audio_paths)

        out_mp4 = VIDEOS_DIR / f"{video_id}.mp4"
        render_video_ffmpeg(frames_folder, final_audio, out_mp4)

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
        supabase.table("videos").update({
            "status": "failed",
            "error": str(e)
        }).eq("id", video_id).execute()

        raise HTTPException(status_code=500, detail=str(e))

# =========================
# API: LIST VIDEOS
# =========================
@router.get("/videos")
def list_videos():
    res = supabase.table("videos").select("*").order("created_at", desc=True).limit(20).execute()
    return res.data
