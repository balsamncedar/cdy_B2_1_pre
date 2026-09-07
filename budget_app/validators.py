from __future__ import annotations

from datetime import datetime

from .errors import AppError


def validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise AppError("날짜 형식이 올바르지 않습니다.", "예: 2024-01-15") from exc
    return value


def validate_month(value: str) -> str:
    try:
        datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise AppError("월 형식이 올바르지 않습니다.", "예: 2024-01") from exc
    return value


def validate_type(value: str) -> str:
    if value not in {"income", "expense"}:
        raise AppError("타입은 income 또는 expense여야 합니다.")
    return value


def validate_amount(value: str | int) -> int:
    try:
        amount = int(value)
    except (TypeError, ValueError) as exc:
        raise AppError("금액은 정수여야 합니다.", "예: 15000") from exc
    if amount <= 0:
        raise AppError("금액은 0보다 커야 합니다.")
    return amount


def parse_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]
