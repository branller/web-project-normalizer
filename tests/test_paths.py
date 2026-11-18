import tempfile
import unittest
from pathlib import Path

from normalizer.paths import resolve_inside, PathSafetyError


class PathSafetyTests(unittest.TestCase):
    def test_allows_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self.assertEqual(resolve_inside(base, "src/file.css"), (base / "src/file.css").resolve())

    def test_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            with self.assertRaises(PathSafetyError):
                resolve_inside(base, "../outside.txt")


if __name__ == "__main__":
    unittest.main()
