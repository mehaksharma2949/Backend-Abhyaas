from fastapi import APIRouter
from pydantic import BaseModel
from openai import OpenAI
import os
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import uuid


router = APIRouter(tags=["Lesson Plan"])

# OpenAI Key
key = os.getenv("OPENAI_API_KEY")
if not key:
    raise RuntimeError("OPENAI_API_KEY is missing. Please set it in backend/.env")

client = OpenAI(api_key=key)


class LessonReq(BaseModel):
    topic: str
    grade: str
    duration: str
    teaching_style: str = "Interactive"
    difficulty: str = "Medium"
    extra: str = ""


def build_prompt(req: LessonReq) -> str:
    return f"""
You are a professional school teacher.

Create a COMPLETE CHAPTER PLAN for Grade/Class {req.grade} students only.
Keep it strictly at their textbook level (NCERT/State board). No advanced content.

Topic/Chapter: {req.topic}
Grade/Class: {req.grade}
Daily Class Duration: {req.duration}
Teaching Style: {req.teaching_style}
Difficulty: {req.difficulty}
Extra Instructions: {req.extra}

VERY IMPORTANT OUTPUT RULES:
1) Output must be neat and clean.
2) Do NOT use markdown (#, ##, ###).
3) Use simple headings like:
   "Chapter Overview", "Week 1", "Day 1", etc.
4) First, decide the total number of weeks needed for the full chapter.
5) Then create a week-wise + day-wise plan.
6) Each day must feel different (not repeated).
7) Follow this daily pattern:

Day 1 = Teaching + Explanation + Board Work
Day 2 = New concept + Examples + Interactive Q/A
Day 3 = Activity / Group Work
Day 4 = Worksheet / Practice
Day 5 = MCQ Quiz + Recap + Doubts

8) Divide time inside each day according to {req.duration}.
9) Teaching Style must influence the plan strongly:
   - Lecture: more teacher explanation
   - Interactive: more questions and student talk
   - Storytelling: story based explanation
   - Activity Based: more hands-on work
   - Project Based: mini project + task-based learning

OUTPUT FORMAT (must follow exactly):

CHAPTER LESSON PLAN

Chapter Name:
Subject:
Grade/Class:
Daily Duration:
Teaching Style:
Difficulty:

1) Chapter Breakdown (Sub-topics)
(List sub-topics in order)

2) Total Weeks Required
(Example: This chapter will take 3 weeks)

3) Week-wise + Day-wise Plan

Week 1:
Day 1 (Teaching Day):
- Sub-topic:
- Time breakup:
- Teacher explains:
- Board work points:
- Student task:
- 5 simple questions:
- Homework:

Day 2 (Concept + Examples Day):
- Sub-topic:
- Time breakup:
- Teacher explains with examples:
- Real-life examples:
- Interactive Q/A:
- Homework:

Day 3 (Activity Day):
- Activity name:
- Aim:
- Materials:
- Steps:
- Expected learning:
- Homework:

Day 4 (Worksheet Day):
- Worksheet (Printable):
  Fill in blanks (5)
  True/False (5)
  Match (5)
  Short answers (3)

Day 5 (Quiz + Recap Day):
- MCQ Quiz (10)
- Answer Key
- Recap points:
- Doubt questions:
- Homework review checklist:

Week 2:
(Repeat same pattern Day 1 to Day 5 with new sub-topics)

Week 3:
(Repeat same pattern Day 1 to Day 5 with new sub-topics)

Final Chapter Test:
- MCQs (15)
- Short answers (8)
- Long answers (2)

Mini Project (End of Chapter):
- Project title:
- Goal:
- Materials:
- Steps:
- Final outcome:
- Rubric (how teacher will check):
"""


@router.post("/generate")
def generate_lesson(req: LessonReq):

    prompt = build_prompt(req)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You create clear and structured lesson plans."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    return {"lesson_plan": response.choices[0].message.content}


@router.post("/download-pdf")
def download_pdf(req: LessonReq):

    plan = generate_lesson(req)["lesson_plan"]

    filename = f"lesson_plan_{uuid.uuid4().hex}.pdf"
    filepath = filename

    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    textobject = c.beginText(40, height - 50)
    textobject.setFont("Helvetica", 11)

    for line in plan.split("\n"):
        if textobject.getY() < 60:
            c.drawText(textobject)
            c.showPage()
            textobject = c.beginText(40, height - 50)
            textobject.setFont("Helvetica", 11)
        textobject.textLine(line)

    c.drawText(textobject)
    c.save()

    return FileResponse(filepath, media_type="application/pdf", filename="LessonPlan.pdf")
    