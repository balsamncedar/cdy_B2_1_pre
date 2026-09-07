from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from .errors import AppError
from .models import Transaction


class DataStore:
    """세 JSONL 파일의 생성과 파일 입출력을 담당한다."""

    DEFAULT_CATEGORIES = ("food", "transport", "rent", "salary", "etc")

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.transactions_path = data_dir / "transactions.jsonl"
        self.categories_path = data_dir / "categories.jsonl"
        self.budgets_path = data_dir / "budgets.jsonl"
        self._initialize()

    def _initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.transactions_path, self.categories_path, self.budgets_path):
            path.touch(exist_ok=True)
        if self.categories_path.stat().st_size == 0:
            self._atomic_write(
                self.categories_path,
                ({"name": name} for name in self.DEFAULT_CATEGORIES),
            )

    @staticmethod
    def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
        with path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, 1):
                if not line.strip():
                    continue
                try:
                    yield json.loads(line)
                except (json.JSONDecodeError, TypeError) as exc:
                    raise AppError(
                        f"저장 파일이 손상되었습니다: {path.name} {line_number}행",
                        "손상된 행을 수정하거나 백업 파일로 복구하세요.",
                    ) from exc

    @staticmethod
    def _read_lines_reverse(path: Path, chunk_size: int = 8192) -> Iterator[str]:
        """파일 전체를 메모리에 올리지 않고 마지막 줄부터 생성한다."""
        with path.open("rb") as file:
            file.seek(0, os.SEEK_END)
            position = file.tell()
            remainder = b""
            while position > 0:
                size = min(chunk_size, position)
                position -= size
                file.seek(position)
                block = file.read(size) + remainder
                lines = block.split(b"\n")
                remainder = lines[0]
                for line in reversed(lines[1:]):
                    if line.strip():
                        yield line.decode("utf-8")
            if remainder.strip():
                yield remainder.decode("utf-8")

    @staticmethod
    def _atomic_write(path: Path, rows: Iterator[dict[str, Any]]) -> None:
        fd, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                for row in rows:
                    file.write(json.dumps(row, ensure_ascii=False) + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_name, path)
        except Exception:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
            raise

    def stream_transactions(self, newest_first: bool = False) -> Iterator[Transaction]:
        if newest_first:
            for line in self._read_lines_reverse(self.transactions_path):
                try:
                    yield Transaction.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise AppError("거래 저장 파일이 손상되었습니다.") from exc
        else:
            # """
            # 일반 순서로 거래를 읽을 때 Transaction.from_dict()의 KeyError, ValueError 등을 AppError로 변환하지 않습니다.
            # 따라서 손상된 거래 파일을 summary, update, delete 등이 읽으면 데코레이터가 잡지 못하고 스택트레이스가 출력될 가능성이 있습니다. 이는 “오류는 스택트레이스 대신 원인과 해결 힌트로 출력” 요구사항과 직접 충돌
            # """
            for row in self._read_jsonl(self.transactions_path):
                yield Transaction.from_dict(row)

    def append_transaction(self, transaction: Transaction) -> None:
        with self.transactions_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(transaction.to_dict(), ensure_ascii=False) + "\n")

    def find_transaction(self, transaction_id: str) -> Transaction | None:
        return next((tx for tx in self.stream_transactions() if tx.id == transaction_id), None)

    def rewrite_transactions(self, transform: Callable[[Transaction], Transaction | None]) -> None:
        def rows() -> Iterator[dict[str, Any]]:
            for transaction in self.stream_transactions():
                changed = transform(transaction)
                if changed is not None:
                    yield changed.to_dict()

        self._atomic_write(self.transactions_path, rows())

    def categories(self) -> list[str]:
        return [str(row["name"]) for row in self._read_jsonl(self.categories_path)]

    def save_categories(self, categories: list[str]) -> None:
        self._atomic_write(self.categories_path, ({"name": name} for name in categories))

    def budgets(self) -> dict[str, int]:
        return {str(row["month"]): int(row["amount"]) for row in self._read_jsonl(self.budgets_path)}

    def save_budget(self, month: str, amount: int) -> None:
        budgets = self.budgets()
        budgets[month] = amount
        self._atomic_write(
            self.budgets_path,
            ({"month": key, "amount": budgets[key]} for key in sorted(budgets)),
        )

