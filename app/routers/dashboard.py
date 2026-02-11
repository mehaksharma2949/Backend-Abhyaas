from fastapi import APIRouter, Depends
from app.core.deps import require_role
from app.models.auth_models import User

router = APIRouter(tags=["Dashboard"])


@router.get("/student")
def student_dashboard(user: User = Depends(require_role("student"))):
    return {"message": f"Welcome Student: {user.name}"}


@router.get("/teacher")
def teacher_dashboard(user: User = Depends(require_role("teacher"))):
    return {"message": f"Welcome Teacher: {user.name}"}

