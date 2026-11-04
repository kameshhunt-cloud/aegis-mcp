import unittest

from server.config import load_role_policies, load_scope_policies, Settings


class TestPolicies(unittest.TestCase):
    def test_role_policies_include_cicd(self) -> None:
        settings = Settings()
        policies = load_role_policies(settings)
        self.assertIn("cicd_pipeline_status", policies.get("admin", []))

    def test_scope_policies_include_cicd(self) -> None:
        settings = Settings()
        policies = load_scope_policies(settings)
        self.assertIn("cicd_pipeline_status", policies.get("aegis.read", []))

    def test_cloudflare_tools_follow_role(self) -> None:
        settings = Settings()
        policies = load_role_policies(settings)
        self.assertIn("cloudflare_search", policies.get("viewer", []))
        self.assertNotIn("cloudflare_execute", policies.get("viewer", []))
        self.assertIn("cloudflare_execute", policies.get("security", []))
        self.assertIn("cloudflare_call", policies.get("admin", []))

    def test_cloudflare_scope_can_execute(self) -> None:
        settings = Settings()
        policies = load_scope_policies(settings)
        self.assertIn("cloudflare_execute", policies.get("aegis.cloudflare", []))
        self.assertNotIn("cloudflare_call", policies.get("aegis.read", []))

    def test_viewer_cannot_access_trivy(self) -> None:
        settings = Settings()
        policies = load_role_policies(settings)
        self.assertNotIn("security_run_trivy_scan", policies.get("viewer", []))


if __name__ == "__main__":
    unittest.main()
