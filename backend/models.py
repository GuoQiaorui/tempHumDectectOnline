from sqlalchemy import Column, Integer, Float, DateTime, String, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from datetime import datetime
import config


Base = declarative_base()


class TemperatureData(Base):
    """温湿度数据表"""
    __tablename__ = "temperature_data"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True)  # 设备 ID
    temperature = Column(Float)  # 温度值 (°C)
    humidity = Column(Float)  # 湿度值 (%)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    raw_data = Column(String(200))  # 原始字节数据 (hex 格式)


class Device(Base):
    """设备信息表"""
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), unique=True, index=True)
    device_name = Column(String(100))
    location = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime)


class User(Base):
    """Application user account."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), default="user", index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class UserDevice(Base):
    """Devices visible to a non-admin user."""
    __tablename__ = "user_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    device_id = Column(String(50), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuthSession(Base):
    """Bearer-token session stored as a token hash."""
    __tablename__ = "auth_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    token_hash = Column(String(128), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, index=True, nullable=False)
    revoked_at = Column(DateTime)


# 创建数据库引擎
engine = create_async_engine(config.config.DATABASE_URL, echo=False)

# 创建会话
async def get_db():
    async with AsyncSession(engine) as session:
        yield session
