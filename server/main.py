from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

from audit.audit_logger import audit_tool_call
from server.auth import authorize_tool, decode_bearer_token
from server.config import load_role_policies, load_scope_policies, load_settings
from tools.aws.ec2 import list_ec2_instances
from tools.aws.s3 import check_s3_public_access
from tools.cicd.pipeline import pipeline_status
from tools.cicd.jenkins import (
    jenkins_list_jobs as _jenkins_list_jobs,
    jenkins_get_job_info as _jenkins_get_job_info,
    jenkins_create_job as _jenkins_create_job,
    jenkins_trigger_build as _jenkins_trigger_build,
    jenkins_get_build_info as _jenkins_get_build_info,
    jenkins_get_build_log as _jenkins_get_build_log,
    jenkins_delete_job as _jenkins_delete_job,
)
from tools.git.repo import get_recent_commits
from tools.kubernetes.pods import list_pods
from tools.kubernetes.audit import k8s_security_audit
from tools.network.headers import check_http_headers
from tools.network.port_scanner import port_scan
from tools.network.ssl_checker import check_ssl_certificate
from tools.security.deps import check_dependencies
from tools.security.secrets import scan_secrets
from tools.security.semgrep import run_semgrep_scan
from tools.security.terraform import scan_terraform
from tools.security.trivy import run_trivy_scan
from tools.cloudflare.api import (
    cloudflare_whoami as _cloudflare_whoami,
    cloudflare_docs as _cloudflare_docs,
    cloudflare_search as _cloudflare_search,
    cloudflare_execute as _cloudflare_execute,
    cloudflare_call as _cloudflare_call,
    cloudflare_generate_report as _cloudflare_generate_report,
)

settings = load_settings()
role_policies = load_role_policies(settings)
scope_policies = load_scope_policies(settings)

mcp = FastMCP(settings.service_name, json_response=True)

AUTH_DISABLED = os.getenv("MCP_AUTH_DISABLED", "false").lower() == "true"


def _authorize(token: str, tool_name: str) -> None:
    if AUTH_DISABLED or not token:
        return
    principal = decode_bearer_token(token, settings)
    authorize_tool(principal, tool_name, role_policies, scope_policies)


@mcp.tool()
@audit_tool_call("aws_list_ec2_instances")
def aws_list_ec2_instances(region: str, token: str = "") -> list[dict]:
    _authorize(token, "aws_list_ec2_instances")
    return list_ec2_instances(region)


@mcp.tool()
@audit_tool_call("k8s_list_pods")
def k8s_list_pods(namespace: str = "default", token: str = "") -> list[dict]:
    _authorize(token, "k8s_list_pods")
    return list_pods(namespace)


@mcp.tool()
@audit_tool_call("k8s_security_audit")
def k8s_security_audit_tool(namespace: str = "", token: str = "") -> list[dict]:
    """Audit Kubernetes clusters for misconfigurations and security risks (privileged containers, hostNetwork, exposed NodePorts, cluster-admin service accounts)."""
    _authorize(token, "k8s_security_audit")
    return k8s_security_audit(namespace)


@mcp.tool()
@audit_tool_call("security_run_trivy_scan")
def security_run_trivy_scan(image: str, token: str = "") -> dict:
    _authorize(token, "security_run_trivy_scan")
    return run_trivy_scan(image)


@mcp.tool()
@audit_tool_call("git_recent_commits")
def git_recent_commits(limit: int = 10, token: str = "") -> list[dict[str, str]]:
    _authorize(token, "git_recent_commits")
    return get_recent_commits(limit)


@mcp.tool()
@audit_tool_call("cicd_pipeline_status")
def cicd_pipeline_status(base_url: str, pipeline_id: str, api_token: str, token: str = "") -> dict:
    """Fetch the status of a CI/CD pipeline."""
    _authorize(token, "cicd_pipeline_status")
    return pipeline_status(base_url, pipeline_id, api_token)


# ── New zero-install tools ─────────────────────────────────────────


@mcp.tool()
@audit_tool_call("security_scan_secrets")
def security_scan_secrets(path: str, token: str = "") -> list[dict]:
    """Scan local files or directories for exposed secrets (API keys, tokens, passwords). This tool runs locally and has full access to the user's local filesystem (e.g. C:\\... paths)."""
    _authorize(token, "security_scan_secrets")
    return scan_secrets(path)


@mcp.tool()
@audit_tool_call("security_check_ssl_certificate")
def security_check_ssl_certificate(hostname: str, port: int = 443, token: str = "") -> dict:
    """Check SSL/TLS certificate details and expiry for a domain."""
    _authorize(token, "security_check_ssl_certificate")
    return check_ssl_certificate(hostname, port)


@mcp.tool()
@audit_tool_call("security_check_dependencies")
def security_check_dependencies(file_path: str, token: str = "") -> list[dict]:
    """Scan dependency files (requirements.txt, package.json) for known vulnerabilities via OSV.dev."""
    _authorize(token, "security_check_dependencies")
    return check_dependencies(file_path)


@mcp.tool()
@audit_tool_call("security_check_http_headers")
def security_check_http_headers(url: str, token: str = "") -> dict:
    """Audit HTTP security headers (HSTS, CSP, X-Frame-Options, etc.) for a URL."""
    _authorize(token, "security_check_http_headers")
    return check_http_headers(url)


@mcp.tool()
@audit_tool_call("aws_check_s3_public_access")
def aws_check_s3_public_access(region: str = "us-east-1", token: str = "") -> list[dict]:
    """Audit S3 buckets for public access settings."""
    _authorize(token, "aws_check_s3_public_access")
    return check_s3_public_access(region)


@mcp.tool()
@audit_tool_call("network_port_scan")
def network_port_scan(host: str, ports: str = "", token: str = "") -> list[dict]:
    """Perform a TCP port scan on common service ports for a host."""
    _authorize(token, "network_port_scan")
    return port_scan(host, ports)


@mcp.tool()
@audit_tool_call("security_semgrep_scan")
def security_semgrep_scan(path: str, config: str = "auto", token: str = "") -> dict:
    """Run a Semgrep SAST scan on a local directory or file. This tool runs locally and has full access to the user's local filesystem (e.g. C:\\... paths). Config can be 'auto', 'p/python', 'p/javascript', etc."""
    _authorize(token, "security_semgrep_scan")
    return run_semgrep_scan(path, config)


# ── Terraform security scanner ─────────────────────────────────────


@mcp.tool()
@audit_tool_call("security_scan_terraform")
def security_scan_terraform(path: str, severity: str = "", token: str = "") -> dict:
    """Scan Terraform (.tf) files for security misconfigurations (S3, IAM, RDS, EC2, networking, encryption, credentials). Optionally filter by severity (CRITICAL, HIGH, MEDIUM, LOW). This tool runs locally and has full access to the user's local filesystem."""
    _authorize(token, "security_scan_terraform")
    return scan_terraform(path, severity)


# ── Jenkins CI/CD tools ────────────────────────────────────────────


@mcp.tool()
@audit_tool_call("jenkins_list_jobs")
def jenkins_list_jobs(url: str, username: str, api_token: str, token: str = "") -> list[dict]:
    """List all jobs on a Jenkins server. Provide the Jenkins URL, username, and API token."""
    _authorize(token, "jenkins_list_jobs")
    return _jenkins_list_jobs(url, username, api_token)


@mcp.tool()
@audit_tool_call("jenkins_get_job_info")
def jenkins_get_job_info(url: str, username: str, api_token: str, job_name: str, token: str = "") -> dict:
    """Get detailed information about a specific Jenkins job including build history and health."""
    _authorize(token, "jenkins_get_job_info")
    return _jenkins_get_job_info(url, username, api_token, job_name)


@mcp.tool()
@audit_tool_call("jenkins_create_job")
def jenkins_create_job(url: str, username: str, api_token: str, job_name: str, config_xml: str = "", token: str = "") -> dict:
    """Create a new Jenkins job. Optionally provide config_xml for the job definition; otherwise a minimal freestyle project is created."""
    _authorize(token, "jenkins_create_job")
    return _jenkins_create_job(url, username, api_token, job_name, config_xml)


@mcp.tool()
@audit_tool_call("jenkins_trigger_build")
def jenkins_trigger_build(url: str, username: str, api_token: str, job_name: str, parameters: str = "", token: str = "") -> dict:
    """Trigger a build for an existing Jenkins job. Optionally pass parameters as a JSON string, e.g. '{"BRANCH": "main"}'."""
    _authorize(token, "jenkins_trigger_build")
    return _jenkins_trigger_build(url, username, api_token, job_name, parameters)


@mcp.tool()
@audit_tool_call("jenkins_get_build_info")
def jenkins_get_build_info(url: str, username: str, api_token: str, job_name: str, build_number: int, token: str = "") -> dict:
    """Get information about a specific Jenkins build including result, duration, and status."""
    _authorize(token, "jenkins_get_build_info")
    return _jenkins_get_build_info(url, username, api_token, job_name, build_number)


@mcp.tool()
@audit_tool_call("jenkins_get_build_log")
def jenkins_get_build_log(url: str, username: str, api_token: str, job_name: str, build_number: int, token: str = "") -> dict:
    """Fetch the console output of a Jenkins build."""
    _authorize(token, "jenkins_get_build_log")
    return _jenkins_get_build_log(url, username, api_token, job_name, build_number)


@mcp.tool()
@audit_tool_call("jenkins_delete_job")
def jenkins_delete_job(url: str, username: str, api_token: str, job_name: str, token: str = "") -> dict:
    """Delete a Jenkins job from the server."""
    _authorize(token, "jenkins_delete_job")
    return _jenkins_delete_job(url, username, api_token, job_name)


# ── Cloudflare API MCP tools ───────────────────────────────────────


@mcp.tool()
@audit_tool_call("cloudflare_whoami")
def cloudflare_whoami(api_token: str = "", endpoint: str = "", token: str = "") -> dict:
    """Show which Cloudflare user or account this API token belongs to."""
    _authorize(token, "cloudflare_whoami")
    return _cloudflare_whoami(api_token, endpoint)


@mcp.tool()
@audit_tool_call("cloudflare_docs")
def cloudflare_docs(query: str, api_token: str = "", endpoint: str = "", token: str = "") -> dict:
    """Search Cloudflare developer documentation through the Cloudflare API MCP server."""
    _authorize(token, "cloudflare_docs")
    return _cloudflare_docs(query, api_token, endpoint)


@mcp.tool()
@audit_tool_call("cloudflare_search")
def cloudflare_search(
    code: str,
    api_token: str = "",
    truncate: bool | None = None,
    endpoint: str = "",
    token: str = "",
) -> dict:
    """Search the Cloudflare OpenAPI spec. ``code`` is an async JavaScript arrow function that reads ``spec.paths``."""
    _authorize(token, "cloudflare_search")
    return _cloudflare_search(code, api_token, truncate, endpoint)


@mcp.tool()
@audit_tool_call("cloudflare_execute")
def cloudflare_execute(
    code: str,
    api_token: str = "",
    account_id: str = "",
    truncate: bool | None = None,
    endpoint: str = "",
    token: str = "",
) -> dict:
    """Call the Cloudflare API. ``code`` is an async JavaScript arrow function that uses ``cloudflare.request()``."""
    _authorize(token, "cloudflare_execute")
    return _cloudflare_execute(code, api_token, account_id, truncate, endpoint)


@mcp.tool()
@audit_tool_call("cloudflare_call")
def cloudflare_call(
    tool_name: str,
    api_token: str = "",
    arguments_json: str = "{}",
    endpoint: str = "",
    token: str = "",
) -> dict:
    """Call any current or future tool on the Cloudflare MCP server. ``arguments_json`` is a JSON object."""
    _authorize(token, "cloudflare_call")
    return _cloudflare_call(tool_name, arguments_json, api_token, endpoint)


@mcp.tool()
@audit_tool_call("cloudflare_generate_report")
def cloudflare_generate_report(
    zone: str,
    days: int = 30,
    output_pdf: str = "",
    output_html: str = "",
    api_token: str = "",
    timezone: str = "SGT",
    token: str = "",
) -> dict:
    """Generate a comprehensive executive PDF & HTML overview report for a Cloudflare zone."""
    _authorize(token, "cloudflare_generate_report")
    return _cloudflare_generate_report(zone, days, output_pdf, output_html, api_token, timezone=timezone)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
