import csv
import tempfile
import unittest
from pathlib import Path

from budget_app.errors import AppError
from budget_app.repositories import DataStore
from budget_app.services import BudgetService


class BudgetServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp.name)
        self.service = BudgetService(DataStore(self.data_dir))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_crud_search_summary_and_budget(self) -> None:
        first = self.service.add_transaction("2024-01-01", "income", "salary", 100000, "급여", "work")
        second = self.service.add_transaction("2024-01-02", "expense", "food", 25000, "점심", "meal")
        self.assertEqual([second.id, first.id], [tx.id for tx in self.service.list_transactions(10)])
        self.assertEqual([second.id], [tx.id for tx in self.service.search(category="food", tag="meal")])

        self.service.set_budget("2024-01", 20000)
        summary = self.service.summary("2024-01", 3)
        self.assertEqual((100000, 25000, 75000), (summary["income"], summary["expense"], summary["balance"]))
        self.assertEqual(20000, summary["budget"])

        updated = self.service.update(second.id, {"amount": "30000", "memo": "저녁"})
        self.assertEqual((30000, "저녁"), (updated.amount, updated.memo))
        self.service.delete(first.id)
        self.assertIsNone(self.service.store.find_transaction(first.id))

    def test_category_rules(self) -> None:
        self.service.add_category("book")
        self.service.add_transaction("2024-02-01", "expense", "book", 1000)
        with self.assertRaises(AppError):
            self.service.remove_category("book")

    def test_export_and_import(self) -> None:
        self.service.add_transaction("2024-03-01", "expense", "food", 5000, "간식", "snack")
        output = self.data_dir / "out.csv"
        self.assertEqual(1, self.service.export_csv(output, "2024-03", None, None))

        other = BudgetService(DataStore(self.data_dir / "other"))
        self.assertEqual((1, 0), other.import_csv(output))
        self.assertEqual(1, len(list(other.store.stream_transactions())))
        with output.open(encoding="utf-8") as file:
            self.assertEqual(["date", "type", "category", "amount", "memo", "tags"], next(csv.reader(file)))

    def test_invalid_input(self) -> None:
        with self.assertRaises(AppError):
            self.service.add_transaction("2024-13-01", "expense", "food", 100)
        with self.assertRaises(AppError):
            self.service.add_transaction("2024-01-01", "expense", "food", 0)


if __name__ == "__main__":
    unittest.main()

