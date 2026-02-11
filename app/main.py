from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.otp import router as otp_router
from app.routers.dashboard import router as dashboard_router
from app.routers.worksheet import router as worksheet_router
from app.routers.diagram import router as diagram_router
from app.routers.fluency import router as fluency_router
from app.routers.story import router as story_router
from app.routers.teachback import router as teachback_router
from app.routers.lesson_plan import router as lesson_plan_router
from app.routers.video_generation import router as video_router
from app.routers.answer_sheet_evaluator import router as answer_sheet_router
from app.routers.auth import router as auth_router



app = FastAPI(title="Abhyaas Backend Full")

# ✅ CORS (frontend connect ke liye)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # deploy ke baad domain restrict kar dena
    allow_credentials=True,
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
app.include_router(auth_router, prefix="/auth")
app.include_router(otp_router, prefix="/otp")
app.include_router(dashboard_router, prefix="/dashboard")

app.include_router(worksheet_router, prefix="/worksheet")
app.include_router(diagram_router, prefix="/diagram")
app.include_router(fluency_router, prefix="/fluency")
app.include_router(story_router, prefix="/story")
app.include_router(teachback_router, prefix="/teachback")
app.include_router(lesson_plan_router, prefix="/lesson-plan")
app.include_router(video_router, prefix="/video")
app.include_router(answer_sheet_router, prefix="/answer-sheet")

