from sqlalchemy import select

from app.core.errors import AppError
from app.database import new_id
from app.models.entities import Task


def list_tasks(session, user):
    query = select(Task).order_by(Task.created_at, Task.id)
    if user.role == "apprentice":
        query = query.where(Task.active_release_id.is_not(None))
    return session.scalars(query).all()


def get_task(session, task_id, user):
    task = session.get(Task, task_id)
    if task is None or (user.role == "apprentice" and task.active_release_id is None):
        raise AppError("TASK_NOT_FOUND", "Task not found.", 404)
    return task


def create_task(session, req, user):
    task = Task(
        id=new_id("task"),
        **req.model_dump(),
        owner_id=user.id,
        source_label="real",
        status="created",
    )
    session.add(task)
    session.flush()
    session.refresh(task)
    return task
