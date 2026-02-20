"""
Database models and connection for PostgreSQL.
"""

import os
from datetime import datetime
from uuid import uuid4
from typing import Optional

from sqlalchemy import (
    create_engine, Column, String, Integer, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from app.core.constants import DATABASE_URL

Base = declarative_base()

# Database engine and session
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Team(Base):
    """Team model."""
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False)
    team_name = Column(String, nullable=False)
    leader_name = Column(String, nullable=False)
    branch_name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    profile = relationship("Profile", back_populates="teams")
    runs = relationship("Run", back_populates="team")


class Profile(Base):
    """Profile model."""
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String)
    created_at = Column(DateTime(timezone=False), default=datetime.utcnow)

    teams = relationship("Team", back_populates="profile")


class Run(Base):
    """Run model."""
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    repo_url = Column(String, nullable=False)
    status = Column(String, nullable=False)
    total_failures = Column(Integer, default=0)
    total_fixes = Column(Integer, default=0)
    iterations_used = Column(Integer, default=0)
    total_time_seconds = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    team = relationship("Team", back_populates="runs")
    ci_timelines = relationship("CITimeline", back_populates="run")
    fixes = relationship("Fix", back_populates="run")


class CITimeline(Base):
    """CI Timeline model."""
    __tablename__ = "ci_timeline"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False)
    iteration_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    run = relationship("Run", back_populates="ci_timelines")

    __table_args__ = (
        CheckConstraint("status IN ('PASSED', 'FAILED')", name='ci_timeline_status_check'),
    )


class Fix(Base):
    """Fix model."""
    __tablename__ = "fixes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"), nullable=False)
    file = Column(String, nullable=False)
    bug_type = Column(String, nullable=False)
    line_number = Column(Integer)
    commit_message = Column(String)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    run = relationship("Run", back_populates="fixes")

    __table_args__ = (
        CheckConstraint("bug_type IN ('LINTING', 'SYNTAX', 'LOGIC', 'TYPE_ERROR', 'IMPORT', 'INDENTATION')", name='fixes_bug_type_check'),
        CheckConstraint("status IN ('FIXED', 'FAILED')", name='fixes_status_check'),
    )


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


# CRUD operations for Run
def create_run(db, team_id: str, repo_url: str, status: str = "PENDING") -> Run:
    """Create a new run."""
    run = Run(
        team_id=team_id,
        repo_url=repo_url,
        status=status
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def update_run_status(db, run_id: str, status: str, total_failures: int = None, 
                      total_fixes: int = None, iterations_used: int = None, 
                      total_time_seconds: int = None):
    """Update run status and metrics."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if run:
        run.status = status
        if total_failures is not None:
            run.total_failures = total_failures
        if total_fixes is not None:
            run.total_fixes = total_fixes
        if iterations_used is not None:
            run.iterations_used = iterations_used
        if total_time_seconds is not None:
            run.total_time_seconds = total_time_seconds
        db.commit()
    return run


# CRUD operations for CI Timeline
def create_ci_timeline(db, run_id: str, iteration_number: int, status: str) -> CITimeline:
    """Create a new CI timeline entry."""
    timeline = CITimeline(
        run_id=run_id,
        iteration_number=iteration_number,
        status=status
    )
    db.add(timeline)
    db.commit()
    db.refresh(timeline)
    return timeline


# CRUD operations for Fix
def create_fix(db, run_id: str, file: str, bug_type: str, line_number: int = None,
               commit_message: str = None, status: str = "FIXED") -> Fix:
    """Create a new fix entry."""
    fix = Fix(
        run_id=run_id,
        file=file,
        bug_type=bug_type,
        line_number=line_number,
        commit_message=commit_message,
        status=status
    )
    db.add(fix)
    db.commit()
    db.refresh(fix)
    return fix


# CRUD operations for Team
def create_team(db, profile_id: str, team_name: str, leader_name: str, branch_name: str) -> Team:
    """Create a new team."""
    team = Team(
        profile_id=profile_id,
        team_name=team_name,
        leader_name=leader_name,
        branch_name=branch_name
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def get_team_by_branch(db, branch_name: str) -> Optional[Team]:
    """Get team by branch name."""
    return db.query(Team).filter(Team.branch_name == branch_name).first()
