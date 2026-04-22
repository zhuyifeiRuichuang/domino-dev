from database.models.base import Base, BaseDatabaseModel
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime


class Workspace(Base, BaseDatabaseModel):
    __tablename__ = "workspace"

    # Table columns
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Git platform settings (generic, replaces github_access_token)
    git_access_token = Column(String, nullable=True)    # encrypted access token
    git_platform_url = Column(String, nullable=True)    # e.g. https://gitlab.mycompany.com
    git_platform_type = Column(String, nullable=True)   # github | gitlab | gitea | bitbucket
    git_username = Column(String, nullable=True)        # for HTTP Basic auth

    # Legacy column – kept for DB migration compatibility; use git_access_token instead
    github_access_token = Column(String, nullable=True)

    users = relationship(
        "UserWorkspaceAssociative",
        back_populates="workspace",
        lazy='subquery',
        uselist=True,
        cascade="all, delete"
    )
    workflows = relationship(
        "Workflow",
        back_populates="workspace",
        lazy='subquery',
        uselist=True,
        cascade="all, delete"
    )
    piece_repositories = relationship(
        "PieceRepository",
        back_populates="workspace",
        lazy='subquery',
        uselist=True,
        cascade="all, delete"
    )
