import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import Storage


class StorageTests(unittest.TestCase):
    def test_dedup_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            s = Storage(td)
            records = [{"id": 1, "name": "a"}, {"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
            written = s.write_jsonl("x.jsonl", records, key_fields=["id"], append=True)
            self.assertEqual(written, 2)


if __name__ == "__main__":
    unittest.main()
