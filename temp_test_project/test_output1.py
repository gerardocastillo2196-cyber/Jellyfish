<write_file path='test_output1.py'>
import unittest
class TestSimple(unittest.TestCase):
    def test_hello(self):
        self.assertEqual(1, 1)
if __name__ == '__main__':
    unittest.main()
</write_file>