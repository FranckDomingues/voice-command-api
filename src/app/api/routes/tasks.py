from itertools import count

from fastapi import APIRouter, HTTPException, status

from src.app.schemas.voice import Task, TaskCreate, TaskReplace, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

# In-memory storage as required by the project.
tasks: list[Task] = []
_next_task_id = count(1)


def find_task(task_id: int) -> Task:
    for task in tasks:
        if task.id == task_id:
            return task

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Task not found",
    )


@router.get("", response_model=list[Task])
def get_tasks() -> list[Task]:
    return tasks


@router.post(
    "",
    response_model=Task,
    status_code=status.HTTP_201_CREATED,
)
def create_task(payload: TaskCreate) -> Task:
    task = Task(
        id=next(_next_task_id),
        title=payload.title,
        done=payload.done,
    )
    tasks.append(task)
    return task


@router.put("/{task_id}", response_model=Task)
def replace_task(task_id: int, payload: TaskReplace) -> Task:
    task = find_task(task_id)
    task.title = payload.title
    task.done = payload.done
    return task


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: int, payload: TaskUpdate) -> Task:
    task = find_task(task_id)

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )
        setattr(task, field, value)

    return task


@router.delete("/{task_id}")
def delete_task(task_id: int) -> dict[str, str]:
    task = find_task(task_id)
    tasks.remove(task)
    return {"message": "Task deleted successfully"}
