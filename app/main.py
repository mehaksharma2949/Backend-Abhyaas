from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    auth, otp, dashboard,
    worksheet, diagram, fluency,
    story, teachback, lesson_plan,
    video_generation, answer_sheet_evaluator,doubt_solver
)

app = FastAPI(title="Abhyaas Backend Full")

# ✅ CORS (frontend connect ke liye)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # deploy ke baad domain restrict kar dena
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Basic routes
@app.get("/")
def home():
    return {"status": "ok", "message": "Abhyaas Backend is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

# ✅ Routers
app.include_router(auth.router, prefix="/auth")
app.include_router(otp.router, prefix="/otp")
app.include_router(dashboard.router, prefix="/dashboard")

app.include_router(worksheet.router, prefix="/worksheet")
app.include_router(diagram.router, prefix="/diagram")
app.include_router(fluency.router, prefix="/fluency")
app.include_router(story.router, prefix="/story")
app.include_router(teachback.router, prefix="/teachback")
app.include_router(lesson_plan.router, prefix="/lesson-plan")
app.include_router(video_generation.router, prefix="/video")
app.include_router(answer_sheet_evaluator.router, prefix="/answer-sheet")
app.include_router(doubt_solver.router, prefix="/doubt")

