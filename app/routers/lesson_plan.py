from fastapi import APIRouter, HTTPException
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


# =========================
# Grade level mapping
# =========================
def grade_level_rules(grade: str) -> str:
    g = "".join([c for c in grade if c.isdigit()])
    if not g:
        return "Keep it strictly at school level."

    g = int(g)

    if g <= 2:
        return """
LEVEL RULES (Grade 1–2):
- Use very simple words.
- No chemical equations.
- Only real-life objects.
- Very short explanations.
- Activities should be fun and easy.
"""
    elif g <= 5:
        return """
LEVEL RULES (Grade 3–5):
- Simple NCERT level.
- No advanced scientific terms.
- Focus on definitions + examples.
- Very basic reasoning only.
- Activities should be classroom friendly.
"""
    elif g <= 8:
        return """
LEVEL RULES (Grade 6–8):
- NCERT middle school level.
- Allow simple experiments and reasoning.
- Include 2–3 short case-based questions.
- Avoid college-level depth.
"""
    elif g <= 10:
        return """
LEVEL RULES (Grade 9–10):
- NCERT high school level.
- Include deeper explanations.
- Include numericals if topic allows.
- Include HOTS questions.
"""
    else:
        return """
LEVEL RULES (Grade 11–12):
- Senior secondary NCERT level.
- Include conceptual depth.
- Include numericals, derivations if relevant.
- Include exam-style questions.
"""


def build_prompt(req: LessonReq) -> str:
    level_rules = grade_level_rules(req.grade)

    return f"""
You are a highly experienced Indian school teacher.

Create a COMPLETE CHAPTER LESSON PLAN for Grade/Class {req.grade} students ONLY.
Keep it strictly at their NCERT/State Board textbook level.

Topic/Chapter: {req.topic}
Grade/Class: {req.grade}
Daily Class Duration: {req.duration}
Teaching Style: {req.teaching_style}
Difficulty: {req.difficulty}
Extra Instructions: {req.extra}

{level_rules}

VERY IMPORTANT OUTPUT RULES:
1) Output must be neat and clean.
2) Do NOT use markdown (#, ##, ###).
3) Use simple headings only.
4) Add these sections BEFORE week plan:
   - Learning Objectives (5)
   - Prerequisite Knowledge
   - Teaching Aids / Materials
   - Assessment Plan (marks distribution)
   - Differentiation (Weak / Average / Strong students)

5) First decide total weeks required.
6) Then create a week-wise + day-wise plan.
7) Each day must feel different.
8) Follow this weekly pattern strictly:

Day 1 = Teaching + Explanation + Board Work
Day 2 = New concept + Examples + Interactive Q/A
Day 3 = Activity / Group Work
Day 4 = Worksheet / Practice
Day 5 = MCQ Quiz + Recap + Doubts

9) Divide time inside each day according to {req.duration}.
10) Teaching Style must strongly influence the plan:
   - Lecture: more teacher explanation
   - Interactive: more questions and student talk
   - Storytelling: story based explanation
   - Activity Based: more hands-on work
   - Project Based: mini project + task-based learning

11) Make the chapter plan realistic for Indian schools.

OUTPUT FORMAT (must follow exactly):

CHAPTER LESSON PLAN

Chapter Name:
Subject:
Grade/Class:
Daily Duration:
Teaching Style:
Difficulty:

0) Learning Objectives (5)
1) Prerequisite Knowledge
2) Teaching Aids / Materials
3) Assessment Plan (Marks Distribution)
4) Differentiation Plan (Weak / Average / Strong)

5) Chapter Breakdown (Sub-topics)
(List sub-topics in order)

6) Total Weeks Required
(Example: This chapter will take 3 weeks)

7) Week-wise + Day-wise Plan

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
(Repeat same pattern Day 1 to Day 5 with NEW sub-topics)

Week 3:
(Repeat same pattern Day 1 to Day 5 with NEW sub-topics)

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
    try:
        prompt = build_prompt(req)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You create clear, realistic, structured Indian school lesson plans."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )

        return {"lesson_plan": response.choices[0].message.content}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download-pdf")
def download_pdf(req: LessonReq):
    try:
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
