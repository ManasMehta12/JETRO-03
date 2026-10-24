from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user, require_roles
from app.database import get_db
from app.models.schemas import TaskCreate, TaskListOut, TaskOut
from app.services import task_service

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=TaskListOut)
def list_tasks(
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    return TaskListOut(items=task_service.list_tasks(session, user))


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(
    req: TaskCreate,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_roles("expert", "reviewer"))],
):
    with session.begin():
        task = task_service.create_task(session, req, user)
    return task


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: str,
    session: Annotated[Session, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    return task_service.get_task(session, task_id, user)
