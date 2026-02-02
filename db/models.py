from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True) # 익명일 수 있으니 nullable
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sessions = relationship("Session", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # 비로그인 사용자도 가능하게
    topic = Column(String, index=True) # 토론 주제
    status = Column(String, default="active") # active, completed, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계 설정
    user = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String) # user, assistant, system
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    meta_info = Column(JSON, nullable=True) # 추가 정보 (토큰 수 등), 호환성 좋음

    session = relationship("Session", back_populates="messages")
