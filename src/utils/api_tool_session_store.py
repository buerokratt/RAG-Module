"""Redis-backed session store for the API Tool Calling agentic loop."""

from typing import Any, Optional

from fastapi import HTTPException, Request, status
from loguru import logger
from redis import WatchError

from models.session_models import APIToolSession
from src.utils.redis_client import get_redis_client

_SESSION_KEY_PREFIX = "session:"
_SESSION_TTL_SECONDS = 1800  # 30 minutes, sliding
_UPDATE_MAX_RETRIES = 3


def _key(chat_id: str) -> str:
    return f"{_SESSION_KEY_PREFIX}{chat_id}"


_VALID_SESSION_FIELDS = frozenset(APIToolSession.model_fields)


class APIToolSessionStore:
    """CRUD store for API tool agentic-loop sessions backed by Redis.

    All operations are async and safe to call from FastAPI handlers.
    The TTL is reset (sliding expiry) on every save() and update().
    """

    async def get(self, chat_id: str) -> Optional[APIToolSession]:
        """Retrieve a session by chat_id.

        Returns:
            The deserialized session, or None if not found / Redis unavailable.
        """
        client = get_redis_client()
        if client is None:
            logger.warning(
                "[SessionStore] Redis unavailable - get({}) skipped", chat_id
            )
            return None

        try:
            raw = await client.get(_key(chat_id))
            if raw is None:
                return None
            return APIToolSession.model_validate_json(raw)
        except Exception as exc:
            logger.error("[SessionStore] get({}) failed: {}", chat_id, exc)
            return None

    async def save(self, session: APIToolSession) -> None:
        """Persist a session (full replace) and reset the TTL.

        Args:
            session: The session object to persist.
        """
        client = get_redis_client()
        if client is None:
            logger.warning(
                "[SessionStore] Redis unavailable - save({}) skipped", session.chat_id
            )
            return

        try:
            await client.set(
                _key(session.chat_id),
                session.model_dump_json(),
                ex=_SESSION_TTL_SECONDS,
            )
            logger.debug("[SessionStore] Session saved for chat_id={}", session.chat_id)
        except Exception as exc:
            logger.error("[SessionStore] save({}) failed: {}", session.chat_id, exc)

    async def update(self, chat_id: str, **fields: Any) -> Optional[APIToolSession]:
        """Atomically update a session using optimistic locking (WATCH/MULTI/EXEC).

        Uses Redis WATCH to detect concurrent modifications. If a conflicting
        write is detected, the operation retries up to ``_UPDATE_MAX_RETRIES`` times.

        Args:
            chat_id: The conversation to update.
            **fields: Field names and new values to merge into the session.

        Returns:
            The updated session, or None if the session does not exist or Redis is unavailable.

        Raises:
            ValueError: If any of the provided field names are not valid
                ``APIToolSession`` attributes.
        """
        unknown = set(fields) - _VALID_SESSION_FIELDS
        if unknown:
            raise ValueError(f"Unknown session fields: {unknown}")

        client = get_redis_client()
        if client is None:
            logger.warning(
                "[SessionStore] Redis unavailable - update({}) skipped", chat_id
            )
            return None

        key = _key(chat_id)

        for attempt in range(_UPDATE_MAX_RETRIES):
            try:
                async with client.pipeline(transaction=True) as pipe:
                    await pipe.watch(key)

                    raw = await pipe.get(key)
                    if raw is None:
                        await pipe.unwatch()
                        logger.warning(
                            "[SessionStore] update({}) - session not found, skipping",
                            chat_id,
                        )
                        return None

                    session = APIToolSession.model_validate_json(raw)
                    updated = session.model_copy(update=fields)

                    pipe.multi()
                    pipe.set(key, updated.model_dump_json(), ex=_SESSION_TTL_SECONDS)
                    await pipe.execute()

                    logger.debug(
                        "[SessionStore] Session updated for chat_id={}", chat_id
                    )
                    return updated

            except WatchError:
                logger.debug(
                    "[SessionStore] update({}) - concurrent modification detected, "
                    "retrying (attempt {}/{})",
                    chat_id,
                    attempt + 1,
                    _UPDATE_MAX_RETRIES,
                )
                continue
            except Exception as exc:
                logger.error("[SessionStore] update({}) failed: {}", chat_id, exc)
                return None

        logger.error(
            "[SessionStore] update({}) - exhausted {} retries due to concurrent writes",
            chat_id,
            _UPDATE_MAX_RETRIES,
        )
        return None

    async def delete(self, chat_id: str) -> None:
        """Remove a session from Redis.

        Args:
            chat_id: The conversation whose session should be deleted.
        """
        client = get_redis_client()
        if client is None:
            logger.warning(
                "[SessionStore] Redis unavailable - delete({}) skipped", chat_id
            )
            return

        try:
            await client.delete(_key(chat_id))
            logger.debug("[SessionStore] Session deleted for chat_id={}", chat_id)
        except Exception as exc:
            logger.error("[SessionStore] delete({}) failed: {}", chat_id, exc)

    async def exists(self, chat_id: str) -> bool:
        """Check whether a session exists for the given chat_id.

        Returns:
            True if the session key exists in Redis, False otherwise.
        """
        client = get_redis_client()
        if client is None:
            return False

        try:
            return bool(await client.exists(_key(chat_id)))
        except Exception as exc:
            logger.error("[SessionStore] exists({}) failed: {}", chat_id, exc)
            return False


def require_session_store(request: Request) -> APIToolSessionStore:
    """FastAPI dependency that guarantees a live session store.

    Use as a dependency on any endpoint that requires multi-turn session
    state.  Returns HTTP 503 immediately when Redis is unavailable instead
    of letting the request silently degrade.
    """
    store: Optional[APIToolSessionStore] = getattr(
        request.app.state, "session_store", None
    )
    if store is None:
        logger.error(
            "[SessionStore] Session store unavailable — returning 503 for {}",
            request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session store is currently unavailable. Please try again later.",
        )
    return store
