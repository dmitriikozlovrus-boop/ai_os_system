import threading
import unittest
from tempfile import TemporaryDirectory

from conductor.interactions import InteractionStore


class FeedbackConcurrencyTest(unittest.TestCase):
    def test_concurrent_duplicate_signals_do_not_duplicate(self):
        with TemporaryDirectory() as tmp:
            store = InteractionStore(f"{tmp}/i.json")
            signal = {"original": "Ты часто теряешь даты"}
            results = []

            def add():
                results.append(store.remember_feedback_signal("imp", signal))

            threads = [threading.Thread(target=add) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(len(store.feedback_signals("imp")), 1)
            self.assertEqual(sum(1 for item in results if item), 1)


if __name__ == "__main__":
    unittest.main()
