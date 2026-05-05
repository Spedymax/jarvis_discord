"""User-facing exceptions raised from cogs/UI; never leak tracebacks to users."""
from __future__ import annotations


class JarvisError(Exception):
    """Base for all Jarvis user-facing errors."""

    user_message: str = "Что-то пошло не так."

    def __init__(self, user_message: str | None = None) -> None:
        super().__init__(user_message or self.user_message)
        if user_message:
            self.user_message = user_message


class NotInVoiceError(JarvisError):
    user_message = "Зайди в голосовой канал."


class WrongVoiceChannelError(JarvisError):
    user_message = "Ты не в том же голосовом канале, что и бот."


class InvalidQueryError(JarvisError):
    user_message = "Не понял запрос — пришли ссылку или название."


class TrackNotFoundError(JarvisError):
    user_message = "По этому запросу ничего не нашёл."


class NotPlayingError(JarvisError):
    user_message = "Сейчас ничего не играет."


class NodeUnavailableError(JarvisError):
    user_message = "Музыкальный сервер сейчас недоступен. Попробуй через несколько секунд."
