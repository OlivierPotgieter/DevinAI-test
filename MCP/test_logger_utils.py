import json
import os
import tempfile
import importlib
import unittest
import logger_utils

class TestLoggerUtils(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["MCP_LOG_DIR"] = self.tmp.name
        importlib.reload(logger_utils)
        self.logger = logger_utils.get_logger()
        for h in list(self.logger.handlers):
            h.close()
            self.logger.removeHandler(h)
        if logger_utils.LOG_FILE.exists():
            logger_utils.LOG_FILE.unlink()
        self.logger = logger_utils.get_logger()  # re-create handler

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("MCP_LOG_DIR", None)

    def test_log_call_creates_json_entry(self):
        logger_utils.log_call("tool", {"token": "abc", "value": 1}, {"result": 42})
        self.assertTrue(logger_utils.LOG_FILE.exists())
        with logger_utils.LOG_FILE.open() as fh:
            line = fh.readline()
        data = json.loads(line)
        self.assertEqual(data["name"], "tool")
        self.assertEqual(data["request"]["value"], 1)
        self.assertEqual(data["response"]["result"], 42)
        self.assertEqual(data["request"]["token"], "[REDACTED]")
        self.assertIn("timestamp", data)
        self.assertIn("module", data)

if __name__ == "__main__":
    unittest.main()
