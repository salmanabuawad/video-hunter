from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import Project, User
from app.schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
):
    if user.role == "admin":
        rows = session.exec(select(Project).order_by(Project.updated_at.desc())).all()
    else:
        rows = session.exec(
            select(Project)
            .where(Project.owner_id == user.id)
            .order_by(Project.updated_at.desc())
        ).all()
    return rows


@router.post("", response_model=ProjectOut)
def create_project(
    body: ProjectCreate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name is required")
    project = Project(name=name, owner_id=user.id)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role != "admin" and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your project")
    return project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role != "admin" and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not your project")
    session.delete(project)
    session.commit()
    return {"ok": True}
