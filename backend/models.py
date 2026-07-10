from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from database import Base

class JobStatus(enum.Enum):
    PENDING = "PENDING"       # Czeka na Workera
    PROCESSING = "PROCESSING" # Worker tnie PDF i pyta AI
    COMPLETED = "COMPLETED"   # Gotowe
    FAILED = "FAILED"         # Wystąpił błąd

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    password_hash = Column(String(255))
    
    activities = relationship("ActivityLog", back_populates="user")

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(255)) # np. "Pobrano PDF: Artykuł ID 5"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="activities")

class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255)) # np. "Rocznik Wrocławski 2026"
    issue_number = Column(String(50))
    file_path = Column(String(500)) # Ścieżka do głównego PDF-a w shared_data
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    articles = relationship("Article", back_populates="issue")
    job = relationship("Job", back_populates="issue", uselist=False)

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"))
    title = Column(String(500))
    author = Column(String(255))
    abstract = Column(Text) # Streszczenie od AI
    keywords = Column(String(255)) # Słowa kluczowe od AI
    start_page = Column(Integer)
    end_page = Column(Integer)
    file_path = Column(String(500)) # Ścieżka do wyciętego PDF-a
    
    issue = relationship("Issue", back_populates="articles")

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"))
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    issue = relationship("Issue", back_populates="job")