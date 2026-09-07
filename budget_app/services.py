from __future__ import annotations

import csv
import uuid
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

from .errors import AppError
from .models import Transaction
from .repositories import DataStore
from .validators import parse_tags, validate_amount, validate_date, validate_month, validate_type


class BudgetService:
    """검증과 가계부 업무 규칙을 담당한다."""

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def _require_category(self, category: str) -> str:
        if category not in self.store.categories():
            raise AppError(f"등록되지 않은 카테고리입니다: {category}", "category list/add를 먼저 실행하세요.")
        return category

    def add_transaction(
        self, date: str, tx_type: str, category: str, amount: str | int,
        memo: str = "", tags: str | list[str] = "",
    ) -> Transaction:
        transaction = Transaction(
            id=f"TX-{uuid.uuid4().hex[:8].upper()}",
            date=validate_date(date),
            type=validate_type(tx_type),
            category=self._require_category(category),
            amount=validate_amount(amount),
            memo=memo.strip(),
            tags=parse_tags(tags) if isinstance(tags, str) else tags,
        )
        self.store.append_transaction(transaction)
        return transaction

    def list_transactions(self, limit: int) -> Iterator[Transaction]:
        if limit <= 0:
            raise AppError("--limit은 1 이상이어야 합니다.")
        for index, transaction in enumerate(self.store.stream_transactions(newest_first=True)):
            if index >= limit:
                break
            yield transaction

    def search(
        self, date_from: str | None = None, date_to: str | None = None,
        category: str | None = None, tx_type: str | None = None,
        query: str | None = None, tag: str | None = None,
    ) -> Iterator[Transaction]:
        if date_from:
            validate_date(date_from)
        if date_to:
            validate_date(date_to)
        if date_from and date_to and date_from > date_to:
            raise AppError("--from은 --to보다 늦을 수 없습니다.")
        if tx_type:
            validate_type(tx_type)
        for tx in self.store.stream_transactions(newest_first=True):
            if date_from and tx.date < date_from:
                continue
            if date_to and tx.date > date_to:
                continue
            if category and tx.category != category:
                continue
            if tx_type and tx.type != tx_type:
                continue
            if query and query.lower() not in tx.memo.lower():
                continue
            if tag and tag not in tx.tags:
                continue
            yield tx

    def update(self, transaction_id: str, changes: dict[str, object]) -> Transaction:
        current = self.store.find_transaction(transaction_id)
        if current is None:
            raise AppError(f"없는 거래 id입니다: {transaction_id}")
        if not changes:
            raise AppError("수정할 옵션을 하나 이상 입력하세요.")
        values = current.to_dict()
        if changes.get("date") is not None:
            values["date"] = validate_date(str(changes["date"]))
        if changes.get("type") is not None:
            values["type"] = validate_type(str(changes["type"]))
        if changes.get("category") is not None:
            values["category"] = self._require_category(str(changes["category"]))
        if changes.get("amount") is not None:
            values["amount"] = validate_amount(str(changes["amount"]))
        if changes.get("memo") is not None:
            values["memo"] = str(changes["memo"]).strip()
        if changes.get("tags") is not None:
            values["tags"] = parse_tags(str(changes["tags"]))
        updated = Transaction.from_dict(values)
        self.store.rewrite_transactions(lambda tx: updated if tx.id == transaction_id else tx)
        return updated

    def delete(self, transaction_id: str) -> None:
        if self.store.find_transaction(transaction_id) is None:
            raise AppError(f"없는 거래 id입니다: {transaction_id}")
        self.store.rewrite_transactions(lambda tx: None if tx.id == transaction_id else tx)

    def summary(self, month: str, top: int) -> dict[str, object]:
        validate_month(month)
        if top <= 0:
            raise AppError("--top은 1 이상이어야 합니다.")
        income = expense = count = 0
        by_category: dict[str, int] = defaultdict(int)
        for tx in self.store.stream_transactions():
            if not tx.date.startswith(month + "-"):
                continue
            count += 1
            if tx.type == "income":
                income += tx.amount
            else:
                expense += tx.amount
                by_category[tx.category] += tx.amount
        categories = sorted(by_category.items(), key=lambda item: (-item[1], item[0]))[:top]
        return {
            "count": count, "income": income, "expense": expense,
            "balance": income - expense, "categories": categories,
            "budget": self.store.budgets().get(month),
        }

    def set_budget(self, month: str, amount: str | int) -> None:
        self.store.save_budget(validate_month(month), validate_amount(amount))

    def get_budget(self, month: str) -> int | None:
        return self.store.budgets().get(validate_month(month))

    def add_category(self, name: str) -> None:
        name = name.strip()
        if not name or any(character.isspace() for character in name):
            raise AppError("카테고리명은 공백 없는 문자열이어야 합니다.")
        categories = self.store.categories()
        if name in categories:
            raise AppError(f"이미 존재하는 카테고리입니다: {name}")
        self.store.save_categories(categories + [name])

    def remove_category(self, name: str) -> None:
        categories = self.store.categories()
        if name not in categories:
            raise AppError(f"없는 카테고리입니다: {name}")
        if any(tx.category == name for tx in self.store.stream_transactions()):
            raise AppError(f"사용 중인 카테고리는 삭제할 수 없습니다: {name}", "거래의 카테고리를 먼저 수정하세요.")
        self.store.save_categories([category for category in categories if category != name])

    def import_csv(self, source: Path) -> tuple[int, int]:
        if not source.is_file():
            raise AppError(f"CSV 파일을 찾을 수 없습니다: {source}")
        imported = skipped = 0
        with source.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            required = {"date", "type", "category", "amount", "memo", "tags"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise AppError("CSV 헤더가 올바르지 않습니다.", "README의 CSV 스키마를 확인하세요.")
            for row in reader:
                try:
                    self.add_transaction(
                        row["date"], row["type"], row["category"], row["amount"],
                        row.get("memo", ""), row.get("tags", ""),
                    )
                    imported += 1
                except (AppError, KeyError):
                    skipped += 1
        return imported, skipped

    def export_csv(
        self, output: Path, month: str | None,
        date_from: str | None, date_to: str | None,
    ) -> int:
        if not month and not (date_from or date_to):
            raise AppError("export에는 --month 또는 --from/--to 조건이 필요합니다.")
        if month:
            validate_month(month)
            date_from, date_to = f"{month}-01", f"{month}-31"
        transactions = self.search(date_from=date_from, date_to=date_to)
        output.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with output.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["date", "type", "category", "amount", "memo", "tags"])
            writer.writeheader()
            for tx in transactions:
                writer.writerow({
                    "date": tx.date, "type": tx.type, "category": tx.category,
                    "amount": tx.amount, "memo": tx.memo, "tags": ",".join(tx.tags),
                })
                count += 1
        return count

