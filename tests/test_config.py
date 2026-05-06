import os
import unittest

from src.base_client.client import BaseClient


class ConfigTests(unittest.TestCase):
    def test_base_client_module_structure(self):
        self.assertTrue(hasattr(BaseClient, "__init__"))
        self.assertTrue(hasattr(BaseClient, "create_record"))
        self.assertTrue(hasattr(BaseClient, "list_records"))
        self.assertTrue(hasattr(BaseClient, "create_table"))

    def test_config_example_has_required_sections(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ex_path = os.path.join(root, "config.yaml.example")
        if not os.path.exists(ex_path):
            self.skipTest("config.yaml.example not found")
        import yaml
        with open(ex_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f.read()) or {}
        self.assertIn("llm", cfg)
        self.assertIn("bot", cfg)
        self.assertIn("api_key", cfg.get("llm", {}))
        self.assertIn("endpoint_id", cfg.get("llm", {}))
        self.assertIn("app_id", cfg.get("bot", {}))
        self.assertIn("app_secret", cfg.get("bot", {}))


if __name__ == "__main__":
    unittest.main()
