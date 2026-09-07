from __future__ import annotations

import functools
import sys
from collections.abc import Callable
from typing import Any, TypeVar

from .errors import AppError

R = TypeVar("R")


def friendly_errors(function: Callable[..., R]) -> Callable[..., R]:
    """예상 오류를 스택트레이스 대신 친절한 메시지와 종료 코드로 바꾼다."""
    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except (AppError, OSError) as error:
            hint = error.hint if isinstance(error, AppError) else "파일 경로와 권한을 확인하세요."
            print(f"[오류] {error}", file=sys.stderr)
            print(f"[힌트] {hint}", file=sys.stderr)
            return 1
    return wrapper
