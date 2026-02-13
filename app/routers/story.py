import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from openai import OpenAI
from supabase import create_client, Client

router = APIRouter(tags=["Story"])

load_dotenv()

# =========================
# CONFIG
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found. Set it in environment variables.")

client = OpenAI(api_key=OPENAI_API_KEY)

# ✅ Supabase ENV
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_KEY")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    print("✅ Supabase connected")
else:
    print("⚠️ Supabase not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing)")

# =========================
# FULL NCERT (Class 3–8)
# =========================
NCERT: Dict[str, Dict[str, List[str]]] = {
    "3": {
        "EVS": [
            "Poonam's Day Out","The Plant Fairy","Water O' Water!","Our First School",
            "Chhotu's House","Foods We Eat","Saying Without Speaking","Flying High",
            "It's Raining","What is Cooking?","From Here to There","Work We Do",
            "Sharing Our Feelings","The Story of Food","Making Pots","Games We Play",
            "Here Comes a Letter","A House Like This","Our Friends – Animals","Drop by Drop",
            "Families Can Be Different","Left-Right","A Beautiful Cloth","Web of Life"
        ],
        "English": [
            "Good Morning","The Magic Garden","Bird Talk","Nina and the Baby Sparrows",
            "Little by Little","The Enormous Turnip","Sea Song","A Little Fish Story",
            "The Balloon Man","The Yellow Butterfly","Trains","The Story of the Road",
            "Puppy and I","Little Tiger, Big Tiger","What's in the Mailbox?","My Silly Sister",
            "Don't Tell","He is My Brother","How Creatures Move","The Ship of the Desert"
        ],
    },
    "4": {
        "EVS": [
            "Going to School","Ear to Ear","A Day with Nandu","The Story of Amrita",
            "Anita and the Honeybees","Omana's Journey","From the Window","Reaching Grandmother's House",
            "Changing Families","Hu Tu Tu, Hu Tu Tu","The Valley of Flowers","Changing Times",
            "A River's Tale","Basva's Farm","From Market to Home","A Busy Month",
            "Nandita in Mumbai","Too Much Water, Too Little Water","Abdul in the Garden","Eating Together",
            "Food and Fun","The World in My Home","Pochampalli","Home and Abroad",
            "Spicy Riddles","Defence Officer: Wahida","Chuskit Goes to School"
        ],
        "English": [
            "Wake Up!","Neha's Alarm Clock","Noses","The Little Fir Tree",
            "Run!","Nasruddin's Aim","Why?","Alice in Wonderland",
            "Don't be Afraid of the Dark","Helen Keller"
        ],
    },
    "5": {
        "EVS": [
            "Super Senses","A Snake Charmer's Story","From Tasting to Digesting","Mangoes Round the Year",
            "Seeds and Seeds","Every Drop Counts","Experiments with Water","A Treat for Mosquitoes",
            "Up You Go!","Walls Tell Stories","Sunita in Space","What if it Finishes...?",
            "A Shelter so High!","When the Earth Shook!","Blow Hot, Blow Cold","Who will do this Work?",
            "Across the Wall","No Place for Us?","A Seed Tells a Farmer's Story","Whose Forests?",
            "Like Father, Like Daughter","On the Move Again"
        ],
        "English": [
            "Ice-cream Man","Wonderful Waste!","Teamwork","Flying Together",
            "My Shadow","Robinson Crusoe Discovers a Footprint","Crying","My Elder Brother",
            "The Lazy Frog","Rip Van Winkle","Class Discussion","The Talkative Barber",
            "Topsy-turvy Land","Gulliver's Travels","Nobody's Friend","The Little Bully",
            "Sing a Song of People","Around the World","Malu Bhalu","Who Will be Ningthou?"
        ],
    },
    "6": {
        "Science": [
            "Food: Where Does It Come From?","Components of Food","Fibre to Fabric","Sorting Materials into Groups",
            "Separation of Substances","Changes Around Us","Getting to Know Plants","Body Movements",
            "The Living Organisms and Their Surroundings","Motion and Measurement of Distances","Light, Shadows and Reflections",
            "Electricity and Circuits","Fun with Magnets","Water","Air Around Us","Garbage In, Garbage Out"
        ],
        "SST": [
            "History: What, Where, How and When?","History: On the Trail of the Earliest People","History: From Gathering to Growing Food",
            "History: In the Earliest Cities","History: What Books and Burials Tell Us","History: Kingdoms, Kings and an Early Republic",
            "History: New Questions and Ideas","History: Ashoka, The Emperor Who Gave Up War","History: Vital Villages, Thriving Towns",
            "History: Traders, Kings and Pilgrims","History: New Empires and Kingdoms","History: Buildings, Paintings and Books",
            "Geography: The Earth in the Solar System","Geography: Globe: Latitudes and Longitudes","Geography: Motions of the Earth",
            "Geography: Maps","Geography: Major Domains of the Earth","Geography: Major Landforms of the Earth","Geography: Our Country – India",
            "Civics: Understanding Diversity","Civics: Diversity and Discrimination","Civics: What is Government?",
            "Civics: Key Elements of a Democratic Government","Civics: Panchayati Raj","Civics: Rural Administration",
            "Civics: Urban Administration","Civics: Rural Livelihoods","Civics: Urban Livelihoods"
        ],
        "English": [
            "Who Did Patrick's Homework?","A House, A Home","How the Dog Found Himself a New Master!","The Kite",
            "Taro's Reward","An Indian-American Woman in Space: Kalpana Chawla","Beauty","A Different Kind of School",
            "Where Do All the Teachers Go?","The Wonderful Words","Fair Play","Vocation","A Game of Chance",
            "Desert Animals","The Banyan Tree"
        ],
    },
    "7": {
        "Science": [
            "Nutrition in Plants","Nutrition in Animals","Fibre to Fabric","Heat","Acids, Bases and Salts",
            "Physical and Chemical Changes","Weather, Climate and Adaptations of Animals to Climate","Winds, Storms and Cyclones",
            "Soil","Respiration in Organisms","Transportation in Animals and Plants","Reproduction in Plants","Motion and Time",
            "Electric Current and its Effects","Light","Water: A Precious Resource","Forests: Our Lifeline","Wastewater Story"
        ],
        "SST": [
            "History: Tracing Changes Through a Thousand Years","History: New Kings and Kingdoms","History: The Delhi Sultans",
            "History: The Mughal Empire","History: Rulers and Buildings","History: Towns, Traders and Craftspersons",
            "History: Tribes, Nomads and Settled Communities","History: Devotional Paths to the Divine",
            "History: The Making of Regional Cultures","History: Eighteenth-Century Political Formations",
            "Geography: Environment","Geography: Inside Our Earth","Geography: Our Changing Earth","Geography: Air","Geography: Water",
            "Geography: Natural Vegetation and Wildlife","Geography: Human Environment – Settlement, Transport and Communication",
            "Geography: Human Environment Interactions – The Tropical and the Subtropical Region","Geography: Life in the Deserts",
            "Civics: On Equality","Civics: Role of the Government in Health","Civics: How the State Government Works",
            "Civics: Growing up as Boys and Girls","Civics: Women Change the World","Civics: Understanding Media",
            "Civics: Understanding Advertising","Civics: Markets Around Us","Civics: A Shirt in the Market",
            "Civics: Struggles for Equality"
        ],
        "English": [
            "Three Questions","A Gift of Chappals","Gopal and the Hilsa Fish","The Ashes That Made Trees Bloom",
            "Quality","Trees","Expert Detectives","Mystery of the Talking Fan","The Invention of Vita-Wonk",
            "Dad and the Cat and the Tree","Garden Snake","The Story of Cricket"
        ],
    },
    "8": {
        "Science": [
            "Crop Production and Management","Microorganisms: Friend and Foe","Synthetic Fibres and Plastics","Materials: Metals and Non-metals",
            "Coal and Petroleum","Combustion and Flame","Conservation of Plants and Animals","Cell — Structure and Functions",
            "Reproduction in Animals","Reaching the Age of Adolescence","Force and Pressure","Friction","Sound",
            "Chemical Effects of Electric Current","Some Natural Phenomena","Light","Stars and the Solar System",
            "Pollution of Air and Water"
        ],
        "SST": [
            "History: How, When and Where","History: From Trade to Territory","History: Ruling the Countryside",
            "History: Tribals, Dikus and the Vision of a Golden Age","History: When People Rebel (1857 and After)",
            "History: Civilising the 'Native', Educating the Nation","History: Women, Caste and Reform",
            "History: The Making of the National Movement: 1870s–1947","History: India After Independence",
            "Geography: Resources","Geography: Land, Soil, Water, Natural Vegetation and Wildlife Resources",
            "Geography: Mineral and Power Resources","Geography: Agriculture","Geography: Industries","Geography: Human Resources",
            "Civics: The Indian Constitution","Civics: Understanding Secularism","Civics: Why Do We Need a Parliament?",
            "Civics: Understanding Laws","Civics: Judiciary","Civics: Understanding Our Criminal Justice System",
            "Civics: Understanding Marginalisation","Civics: Confronting Marginalisation","Civics: Public Facilities",
            "Civics: Law and Social Justice"
        ],
        "English": [
            "The Best Christmas Present in the World","The Tsunami","Glimpses of the Past","Glimpses of the Past",
            "Bepin Choudhury's Lapse of Memory","The Summit Within","This is Jody's Fawn","A Visit to Cambridge",
            "A Short Monsoon Diary","The Great Stone Face – I","The Great Stone Face – II"
        ],
    },
}

# =========================
# HELPERS
# =========================
def normalize(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("’", "'").replace("–", "-")
    s = re.sub(r"\s+", " ", s)
    return s

def build_flat_index() -> List[dict]:
    items = []
    for cls, subs in NCERT.items():
        for subject, chapters in subs.items():
            for ch in chapters:
                items.append({
                    "class_level": cls,
                    "subject": subject,
                    "chapter": ch,
                    "chapter_norm": normalize(ch)
                })
    return items

FLAT = build_flat_index()

def best_match(class_level: str, query: str) -> Optional[dict]:
    q = normalize(query)
    pool = [x for x in FLAT if x["class_level"] == class_level]

    for item in pool:
        if item["chapter_norm"] == q:
            return item

    contains = [x for x in pool if q in x["chapter_norm"]]
    if contains:
        contains.sort(key=lambda x: len(x["chapter_norm"]))
        return contains[0]

    q_tokens = set(q.split())
    scored = []
    for item in pool:
        t = set(item["chapter_norm"].split())
        score = len(q_tokens.intersection(t))
        if score > 0:
            scored.append((score, item))

    if scored:
        scored.sort(key=lambda x: (-x[0], len(x[1]["chapter_norm"])))
        return scored[0][1]

    return None

def safe_json_parse(text: str) -> dict:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError("Could not find JSON in model response")
    return json.loads(m.group(0))

# =========================
# REQUEST MODEL
# =========================
class StoryByChapterNameRequest(BaseModel):
    class_level: str
    chapter_name: str
    language: str = "Hindi"
    style: str = "Warm Teacher"
    length: str = "Full"

# =========================
# PROMPT
# =========================
def build_story_prompt(class_level: str, subject: str, chapter: str, language: str, style: str, length: str) -> str:
    return f"""
You are a very kind Indian government school teacher.
You teach NCERT in a simple and friendly way.

TASK:
Write a full chapter story that teaches the NCERT chapter concept.

STUDENT LEVEL:
Class {class_level} (very simple language).

STRICT RULES:
- Must be aligned to NCERT chapter: "{chapter}".
- Subject: {subject}
- This is FULL CHAPTER STORY mode.
- Story must be 7 to 10 minutes when read aloud.
- Write in 6 scenes. Each scene must have a heading like: "Scene 1:", "Scene 2:" etc.
- Use a continuous story with characters (2 kids + 1 teacher OR 1 grandparent).
- Cover ALL key points of the chapter in story form (not summary).
- Use simple words, short sentences, and Indian daily-life examples.

- Always add "timeline_or_steps":
  - If History: include YEAR + EVENT
  - If Civics: include STEP + meaning
  - If Geography: include LOCATION/FEATURE + meaning
  - If Science/EVS: include PROCESS steps
  - If English: include STORY SEQUENCE + 5 vocab words

- Always add "memory_tricks" in simple Hindi/English.

- Use language: {language}
- Style: {style}

OUTPUT MUST BE JSON ONLY (no markdown, no extra text):
{{
  "title": "...",
  "story": "...",
  "concept_recap": ["...", "...", "...", "...", "..."],
  "timeline_or_steps": [
    {{"key":"...", "point":"..."}},
    {{"key":"...", "point":"..."}},
    {{"key":"...", "point":"..."}}
  ],
  "memory_tricks": [
    "...","...","...","...","...","..."
  ],
  "questions": [
    {{"q": "...", "type": "mcq", "options": ["A","B","C","D"], "answer": "A"}},
    {{"q": "...", "type": "mcq", "options": ["A","B","C","D"], "answer": "A"}},
    {{"q": "...", "type": "short", "answer": "..."}},
    {{"q": "...", "type": "short", "answer": "..."}},
    {{"q": "...", "type": "short", "answer": "..."}}
  ],
  "activity": "..."
}}
""".strip()

# =========================
# ROUTES (router based ✅)
# =========================
@router.get("/")
def root():
    return {"ok": True, "service": "Story router working"}

@router.get("/api/classes")
def get_classes():
    return ["3", "4", "5", "6", "7", "8"]

@router.post("/api/story_by_name")
def story_by_name(req: StoryByChapterNameRequest):
    if req.class_level not in NCERT:
        raise HTTPException(status_code=400, detail="Invalid class")

    if not req.chapter_name or len(req.chapter_name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Chapter name is required")

    match = best_match(req.class_level, req.chapter_name)
    if not match:
        pool = [x for x in FLAT if x["class_level"] == req.class_level]
        suggestions = [x["chapter"] for x in pool][:20]
        raise HTTPException(
            status_code=404,
            detail=f"Chapter not found. Example chapters: {', '.join(suggestions[:10])}"
        )

    prompt = build_story_prompt(
        class_level=match["class_level"],
        subject=match["subject"],
        chapter=match["chapter"],
        language=req.language,
        style=req.style,
        length=req.length
    )

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You output only valid JSON. No markdown."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
        )

        raw = resp.choices[0].message.content
        data = safe_json_parse(raw)

        # SAVE TO SUPABASE
        saved_id = None
        if supabase is not None:
            try:
                insert_payload = {
                    "class_level": match["class_level"],
                    "language": req.language,
                    "style": req.style,
                    "length": req.length,
                    "chapter_query": req.chapter_name,
                    "matched_subject": match["subject"],
                    "matched_chapter": match["chapter"],
                    "story_json": data,
                    "audio_url": None
                }

                db_res = supabase.table("stories").insert(insert_payload).execute()
                if db_res.data and len(db_res.data) > 0:
                    saved_id = db_res.data[0].get("id")

            except Exception as e:
                print("Supabase insert failed:", str(e))

        return JSONResponse({
            "ok": True,
            "matched": {
                "subject": match["subject"],
                "chapter": match["chapter"]
            },
            "data": data,
            "meta": {
                "class": match["class_level"],
                "language": req.language,
                "style": req.style,
                "length": req.length,
                "saved_id": saved_id,
                "generated_at": datetime.utcnow().isoformat() + "Z",
            }
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Story generation failed: {str(e)}")

@router.post("/api/tts")
def tts(payload: dict):
    text = payload.get("text", "")
    voice = payload.get("voice", "nova")

    if not text or len(text.strip()) < 5:
        raise HTTPException(status_code=400, detail="Text is required")

    text = re.sub(r"\s+", " ", text).strip()

    try:
        audio_resp = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=voice,
            input=text
        )
        audio_bytes = audio_resp.read()

        return StreamingResponse(
            iter([audio_bytes]),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=story.mp3"},
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")

@router.get("/api/history")
def history():
    if supabase is None:
        raise HTTPException(status_code=400, detail="Supabase not configured")

    try:
        res = (
            supabase
            .table("stories")
            .select("id, created_at, class_level, language, matched_subject, matched_chapter, chapter_query")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )

        return {"ok": True, "items": res.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History fetch failed: {str(e)}")
