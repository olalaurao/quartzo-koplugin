import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from package import FILES, ROOT, package


class PackageTest(unittest.TestCase):
    def test_exact_allowlist_reproducible_bytes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = (Path(directory) / name for name in ("first.zip", "second.zip"))
            manifest = package(first)
            self.assertEqual(manifest, package(second))
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(manifest["sha256"], hashlib.sha256(first.read_bytes()).hexdigest())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), list(FILES))
                self.assertIsNone(archive.testzip())
                for name in FILES:
                    self.assertEqual(archive.read(name), (ROOT / name).read_bytes())
            with self.assertRaises(FileExistsError):
                package(first)
            self.assertEqual(manifest["sha256"], hashlib.sha256(first.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
