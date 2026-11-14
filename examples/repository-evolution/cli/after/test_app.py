import unittest
from app import parse_count

class CountTest(unittest.TestCase):
    def test_valid_count(self):
        self.assertEqual(parse_count("2"), 2)
