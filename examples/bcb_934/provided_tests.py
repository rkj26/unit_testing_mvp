# BCB/934 PROVIDED TESTS (HuggingFace) — note: 5 hard-coded (word -> hash) cases only

import unittest


class TestCases(unittest.TestCase):
    def test_case_1(self):
        # Test with the word 'abracadabra'
        result = task_func("abracadabra")
        expected = "bc9af285d87b312e61ab3661e66b741b"
        self.assertEqual(result, expected)

    def test_case_2(self):
        # Test with the word 'hello'
        result = task_func("hello")
        expected = "dd5dec1a853625e2dc48f3d42665c337"
        self.assertEqual(result, expected)

    def test_case_3(self):
        # Test with the word 'python'
        result = task_func("python")
        expected = "2ef1af06ae4aa496eaa8e963bde5514e"
        self.assertEqual(result, expected)

    def test_case_4(self):
        # Test with an empty string
        result = task_func("")
        expected = "99914b932bd37a50b983c5e7c90ae93b"
        self.assertEqual(result, expected)

    def test_case_5(self):
        # Test with a single character string
        result = task_func("a")
        expected = "99914b932bd37a50b983c5e7c90ae93b"
        self.assertEqual(result, expected)
