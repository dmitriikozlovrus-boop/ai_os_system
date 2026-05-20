import unittest

from conductor.models import classification_from_dict, normalize_effort


class ModelsTest(unittest.TestCase):
    def test_normalize_effort(self):
        self.assertEqual(normalize_effort(5), "5m")
        self.assertEqual(normalize_effort(14), "15m")
        self.assertEqual(normalize_effort(30), "30m")
        self.assertEqual(normalize_effort(60), "1h")
        self.assertEqual(normalize_effort(90), "2h+")

    def test_classification_from_dict(self):
        data = {
            "tasks": [
                {
                    "title": "Позвонить Марко",
                    "description": "Уточнить алюминий",
                    "desired_result": "Есть следующий шаг",
                    "project": "Сырьевой трейдинг",
                    "area": "Бизнес",
                    "due_date": "2026-05-21",
                    "effort_minutes": 15,
                    "priority": "P2",
                    "next_step": "Позвонить",
                    "confidence": 0.9,
                    "missing": [],
                }
            ],
            "studies": [],
            "notes": [],
        }
        result = classification_from_dict(data)
        self.assertEqual(result.tasks[0].title, "Позвонить Марко")
        self.assertEqual(result.tasks[0].effort_minutes, 15)


if __name__ == "__main__":
    unittest.main()
