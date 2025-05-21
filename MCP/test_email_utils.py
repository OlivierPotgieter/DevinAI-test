import unittest
from email_utils import condense_repetitive_messages

class TestEmailUtils(unittest.TestCase):
    def test_condense_repetitive_messages(self):
        text = (
            "From: a\nSubject: Report\nLabels: Spam\nSnippet1\n\n"
            "From: b\nSubject: Report\nLabels: Spam\nSnippet2\n\n"
            "From: c\nSubject: Update\nLabels: Work\nSnippet3"
        )
        out = condense_repetitive_messages(text)
        # Only one occurrence of the repeated subject should remain
        self.assertEqual(out.count("Subject: Report"), 1)
        # Should annotate the repetition count
        self.assertIn("(x2)", out)
        # Unique subjects preserved
        self.assertIn("Subject: Update", out)
if __name__ == "__main__":
    unittest.main()
