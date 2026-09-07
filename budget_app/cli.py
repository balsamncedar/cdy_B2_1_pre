from __future__ import annotations

import argparse
from pathlib import Path

from .decorators import friendly_errors
from .errors import AppError
from .models import Transaction
from .repositories import DataStore
from .services import BudgetService
from .validators import validate_amount, validate_date, validate_type


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m budget_app", description="나만의 용돈 기입장")
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="저장 폴더 (기본: ./data)")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("add", help="대화형 거래 추가")
    list_parser = commands.add_parser("list", help="최신순 거래 목록")
    list_parser.add_argument("--limit", type=int, default=10)

    search = commands.add_parser("search", help="조건 검색")
    search.add_argument("--from", dest="date_from")
    search.add_argument("--to", dest="date_to")
    search.add_argument("--category")
    search.add_argument("--type", choices=("income", "expense"))
    search.add_argument("--q")
    search.add_argument("--tag")

    summary = commands.add_parser("summary", help="월별 요약")
    summary.add_argument("--month", required=True)
    summary.add_argument("--top", type=int, default=3)

    budget = commands.add_parser("budget", help="예산 설정/조회")
    budget_sub = budget.add_subparsers(dest="action", required=True)
    budget_set = budget_sub.add_parser("set")
    budget_set.add_argument("--month", required=True)
    budget_set.add_argument("--amount", required=True)
    budget_show = budget_sub.add_parser("show")
    budget_show.add_argument("--month", required=True)

    category = commands.add_parser("category", help="카테고리 관리")
    category_sub = category.add_subparsers(dest="action", required=True)
    category_sub.add_parser("list")
    category_add = category_sub.add_parser("add")
    category_add.add_argument("--name")
    category_remove = category_sub.add_parser("remove")
    category_remove.add_argument("--name", required=True)

    update = commands.add_parser("update", help="옵션 방식 거래 수정")
    update.add_argument("--id", required=True)
    update.add_argument("--date")
    update.add_argument("--type", choices=("income", "expense"))
    update.add_argument("--category")
    update.add_argument("--amount")
    update.add_argument("--memo")
    update.add_argument("--tags")

    delete = commands.add_parser("delete", help="거래 삭제")
    delete.add_argument("--id", required=True)

    importer = commands.add_parser("import", help="CSV 가져오기")
    importer.add_argument("--from", dest="source", type=Path, required=True)
    exporter = commands.add_parser("export", help="CSV 내보내기")
    exporter.add_argument("--out", type=Path, required=True)
    exporter.add_argument("--month")
    exporter.add_argument("--from", dest="date_from")
    exporter.add_argument("--to", dest="date_to")
    return parser


def _ask(prompt: str, validator=None) -> str:
    while True:
        value = input(prompt).strip()
        try:
            return validator(value) if validator else value
        except AppError as error:
            print(f"[오류] {error}")
            print(f"[힌트] {error.hint}")


def _print_transaction(tx: Transaction) -> None:
    tags = ",".join(tx.tags)
    print(f"{tx.id} | {tx.date} | {tx.type:<7} | {tx.category} | {tx.amount} | {tx.memo} | {tags}")


@friendly_errors
def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = BudgetService(DataStore(args.data_dir))

    if args.command == "add":
        date = _ask("날짜(YYYY-MM-DD): ", validate_date)
        tx_type = _ask("타입(income/expense): ", validate_type)
        categories = service.store.categories()
        print("카테고리:", ", ".join(categories))
        category = _ask("카테고리: ", service._require_category)
        amount = _ask("금액(양수): ", validate_amount)
        memo = input("메모(선택): ").strip()
        tags = input("태그(쉼표로 구분, 없으면 엔터): ").strip()
        transaction = service.add_transaction(date, tx_type, category, amount, memo, tags)
        print(f"[저장 완료] id={transaction.id}")
    elif args.command == "list":
        transactions = list(service.list_transactions(args.limit))
        if not transactions:
            print("데이터 없음")
        for transaction in transactions:
            _print_transaction(transaction)
    elif args.command == "search":
        found = False
        for transaction in service.search(args.date_from, args.date_to, args.category, args.type, args.q, args.tag):
            found = True
            _print_transaction(transaction)
        if not found:
            print("검색 결과 없음")
    elif args.command == "summary":
        result = service.summary(args.month, args.top)
        if result["count"] == 0:
            print("데이터 없음")
            return 0
        print(f"총 수입: {result['income']}원")
        print(f"총 지출: {result['expense']}원")
        print(f"잔액: {result['balance']}원")
        budget = result["budget"]
        if budget is not None:
            rate = float(result["expense"]) / int(budget) * 100
            print(f"예산: {budget}원 (사용률 {rate:.1f}%)")
            if result["expense"] > budget:
                print("[경고] 예산을 초과했습니다!")
        print(f"\n지출 TOP {args.top}")
        for index, (category, amount) in enumerate(result["categories"], 1):
            print(f"{index}) {category} {amount}원")
    elif args.command == "budget":
        if args.action == "set":
            service.set_budget(args.month, args.amount)
            print(f"[저장 완료] {args.month} 예산 {int(args.amount)}원")
        else:
            amount = service.get_budget(args.month)
            print(f"{args.month} 예산: {amount}원" if amount is not None else "설정된 예산 없음")
    elif args.command == "category":
        if args.action == "list":
            for category in service.store.categories():
                print(f"- {category}")
        elif args.action == "add":
            name = args.name or input("카테고리명: ").strip()
            service.add_category(name)
            print(f"[저장 완료] category={name}")
        else:
            service.remove_category(args.name)
            print(f"[삭제 완료] category={args.name}")
    elif args.command == "update":
        changes = {key: value for key, value in vars(args).items() if key in {"date", "type", "category", "amount", "memo", "tags"} and value is not None}
        transaction = service.update(args.id, changes)
        print(f"[수정 완료] id={transaction.id}")
    elif args.command == "delete":
        service.delete(args.id)
        print(f"[삭제 완료] id={args.id}")
    elif args.command == "import":
        imported, skipped = service.import_csv(args.source)
        print(f"[완료] imported={imported}, skipped={skipped}")
    elif args.command == "export":
        count = service.export_csv(args.out, args.month, args.date_from, args.date_to)
        print(f"[완료] {args.out} ({count} records)")
    return 0

