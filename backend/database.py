import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.future import select

import models
import security

logger = logging.getLogger("database")

async_session_factory = async_sessionmaker(
    models.engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    async with models.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    await ensure_default_accounts()
    logger.info("Database tables and default accounts are ready")


def user_to_dict(user: models.User, devices: Optional[List[str]] = None) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "devices": devices or [],
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


async def _get_user_devices(session: AsyncSession, user_id: int) -> List[str]:
    result = await session.execute(
        select(models.UserDevice.device_id)
        .where(models.UserDevice.user_id == user_id)
        .order_by(models.UserDevice.device_id.asc())
    )
    return list(result.scalars().all())


async def _set_user_devices(session: AsyncSession, user_id: int, device_ids: List[str]):
    normalized = sorted({d.strip().upper() for d in device_ids if d and d.strip()})
    await session.execute(delete(models.UserDevice).where(models.UserDevice.user_id == user_id))
    for device_id in normalized:
        session.add(models.UserDevice(user_id=user_id, device_id=device_id))


async def ensure_default_accounts():
    await ensure_user("admin", "admin123", "admin", [])
    await ensure_user("testuser", "Test12345", "user", ["DEV0001"])


async def ensure_user(username: str, password: str, role: str, device_ids: List[str]):
    async with async_session_factory() as session:
        result = await session.execute(select(models.User).where(models.User.username == username))
        user = result.scalar_one_or_none()
        now = datetime.utcnow()
        if not user:
            user = models.User(
                username=username,
                password_hash=security.hash_password(password),
                role=role,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            await session.flush()
        else:
            user.role = role
            user.is_active = True
            user.updated_at = now
        await _set_user_devices(session, user.id, device_ids)
        await session.commit()


async def authenticate_user(username: str, password: str) -> Optional[dict]:
    async with async_session_factory() as session:
        result = await session.execute(select(models.User).where(models.User.username == username))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return None
        if not security.verify_password(password, user.password_hash):
            return None
        return user_to_dict(user, await _get_user_devices(session, user.id))


async def create_session(user_id: int, token: str, hours: int = 24) -> dict:
    async with async_session_factory() as session:
        auth_session = models.AuthSession(
            user_id=user_id,
            token_hash=security.hash_token(token),
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=hours),
        )
        session.add(auth_session)
        await session.commit()
        return {"expires_at": auth_session.expires_at.isoformat()}


async def get_user_by_token(token: str) -> Optional[dict]:
    if not token:
        return None
    async with async_session_factory() as session:
        result = await session.execute(
            select(models.AuthSession, models.User)
            .join(models.User, models.User.id == models.AuthSession.user_id)
            .where(models.AuthSession.token_hash == security.hash_token(token))
            .where(models.AuthSession.revoked_at.is_(None))
            .where(models.AuthSession.expires_at > datetime.utcnow())
            .where(models.User.is_active.is_(True))
        )
        row = result.first()
        if not row:
            return None
        _, user = row
        return user_to_dict(user, await _get_user_devices(session, user.id))


async def revoke_session(token: str) -> bool:
    async with async_session_factory() as session:
        result = await session.execute(
            update(models.AuthSession)
            .where(models.AuthSession.token_hash == security.hash_token(token))
            .where(models.AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.utcnow())
        )
        await session.commit()
        return result.rowcount > 0


async def list_users() -> List[dict]:
    async with async_session_factory() as session:
        result = await session.execute(select(models.User).order_by(models.User.id.asc()))
        users = result.scalars().all()
        return [user_to_dict(user, await _get_user_devices(session, user.id)) for user in users]


async def create_user(
        username: str,
        password: str,
        role: str = "user",
        device_ids: Optional[List[str]] = None,
) -> dict:
    if role not in {"user", "admin"}:
        raise ValueError("role must be user or admin")
    if not security.validate_password(password):
        raise ValueError("password must be at least 8 characters and contain letters and numbers")
    async with async_session_factory() as session:
        result = await session.execute(select(models.User).where(models.User.username == username))
        if result.scalar_one_or_none():
            raise ValueError("username already exists")
        now = datetime.utcnow()
        user = models.User(
            username=username,
            password_hash=security.hash_password(password),
            role=role,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        await session.flush()
        await _set_user_devices(session, user.id, device_ids or [])
        devices = await _get_user_devices(session, user.id)
        await session.commit()
        return user_to_dict(user, devices)


async def update_user(
        user_id: int,
        password: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        device_ids: Optional[List[str]] = None,
) -> Optional[dict]:
    async with async_session_factory() as session:
        user = await session.get(models.User, user_id)
        if not user:
            return None
        if password:
            if not security.validate_password(password):
                raise ValueError("password must be at least 8 characters and contain letters and numbers")
            user.password_hash = security.hash_password(password)
        if role is not None:
            if role not in {"user", "admin"}:
                raise ValueError("role must be user or admin")
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        if device_ids is not None:
            await _set_user_devices(session, user.id, device_ids)
        user.updated_at = datetime.utcnow()
        devices = await _get_user_devices(session, user.id)
        await session.commit()
        return user_to_dict(user, devices)


async def delete_user(user_id: int) -> bool:
    async with async_session_factory() as session:
        user = await session.get(models.User, user_id)
        if not user or user.role == "admin":
            return False
        await session.execute(delete(models.AuthSession).where(models.AuthSession.user_id == user_id))
        await session.execute(delete(models.UserDevice).where(models.UserDevice.user_id == user_id))
        await session.delete(user)
        await session.commit()
        return True


def visible_devices_for_user(user: dict) -> Optional[List[str]]:
    if user.get("role") == "admin":
        return None
    return list(user.get("devices") or [])


def user_can_access_device(user: dict, device_id: Optional[str]) -> bool:
    if user.get("role") == "admin":
        return True
    if not device_id:
        return False
    return device_id in set(user.get("devices") or [])


async def save_temperature_data(data: dict):
    async with async_session_factory() as session:
        record = models.TemperatureData(
            device_id=data["device_id"],
            temperature=data["temperature"],
            humidity=data["humidity"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            raw_data=data["raw_data"],
        )
        session.add(record)
        await session.commit()


async def get_temperature_history(
        device_id: str,
        hours: int = 24,
        limit: int = 1000,
        allowed_devices: Optional[List[str]] = None,
) -> List[dict]:
    if allowed_devices is not None and device_id not in allowed_devices:
        return []
    async with async_session_factory() as session:
        start_time = datetime.utcnow() - timedelta(hours=hours)
        result = await session.execute(
            select(models.TemperatureData)
            .where(models.TemperatureData.device_id == device_id)
            .where(models.TemperatureData.timestamp >= start_time)
            .order_by(models.TemperatureData.timestamp.asc())
            .limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                "device_id": r.device_id,
                "timestamp": r.timestamp.isoformat(),
                "temperature": r.temperature,
                "humidity": r.humidity,
            }
            for r in records
        ]


async def get_latest_data(
        device_id: Optional[str] = None,
        allowed_devices: Optional[List[str]] = None,
) -> Optional[dict]:
    if allowed_devices is not None:
        if not allowed_devices:
            return None
        if device_id and device_id not in allowed_devices:
            return None
    async with async_session_factory() as session:
        query = select(models.TemperatureData).order_by(models.TemperatureData.timestamp.desc())
        if device_id:
            query = query.where(models.TemperatureData.device_id == device_id)
        if allowed_devices is not None:
            query = query.where(models.TemperatureData.device_id.in_(allowed_devices))
        result = await session.execute(query.limit(1))
        record = result.scalar()
        if record:
            return {
                "device_id": record.device_id,
                "temperature": record.temperature,
                "humidity": record.humidity,
                "timestamp": record.timestamp.isoformat(),
            }
        return None


async def get_device_list(allowed_devices: Optional[List[str]] = None) -> List[dict]:
    async with async_session_factory() as session:
        query = select(models.TemperatureData.device_id).distinct()
        if allowed_devices is not None:
            if not allowed_devices:
                return []
            query = query.where(models.TemperatureData.device_id.in_(allowed_devices))
        result = await session.execute(query)
        device_ids = set(result.scalars().all())
        if allowed_devices is not None:
            device_ids.update(allowed_devices)
        else:
            bound_result = await session.execute(select(models.UserDevice.device_id).distinct())
            device_ids.update(bound_result.scalars().all())
        return [{"device_id": did} for did in sorted(device_ids)]


async def cleanup_old_data(retention_days: int = 90):
    if retention_days <= 0:
        return
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    async with async_session_factory() as session:
        result = await session.execute(
            delete(models.TemperatureData).where(models.TemperatureData.timestamp < cutoff)
        )
        await session.commit()
        deleted = result.rowcount
        if deleted > 0:
            logger.info("Cleaned %d old records before %s", deleted, cutoff.isoformat())
