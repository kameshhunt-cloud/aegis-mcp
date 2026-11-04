<div align="center">
  <img src="docs/aegis-mcp-logo-v2.svg" width="100%" alt="Aegis MCP logo"/>
  <h1>🛡️ Aegis MCP Server</h1>
  <p><b>Aegis MCP is an open-source, DevSecOps-focused Model Context Protocol server that allows AI agents to safely interact with cloud infrastructure, CI/CD systems, and security tooling.</b></p>

  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![Python version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
  [![MCP Protocol](https://img.shields.io/badge/MCP-Server-green.svg)](https://modelcontextprotocol.io/)
  [![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

  <div align="center" style="margin-top: 20px;">
    <a href="https://www.producthunt.com/products/aegis-mcp?embed=true&utm_source=embed&utm_medium=post_embed" target="_blank" rel="noopener">
      <table>
        <tr>
          <td align="center" width="80">
            <img alt="Aegis MCP logo" src="https://ph-files.imgix.net/52e95a48-965f-485c-81ed-cc992e8cbf98.svg?auto=format&fit=crop&w=80&h=80" width="64" height="64" style="border-radius: 8px;">
          </td>
          <td>
            <h3 style="margin: 0; font-size: 18px;">Aegis MCP</h3>
            <p style="margin: 0; font-size: 14px; color: #666;">DevSecOps superpowers for your AI coding assistant</p>
          </td>
        </tr>
        <tr>
          <td colspan="2" align="left">
            <img src="https://img.shields.io/badge/Check%20it%20out%20on%20Product%20Hunt%20%E2%86%92-ff6154?style=for-the-badge" alt="Check it out on Product Hunt" />
          </td>
        </tr>
      </table>
    </a>
  </div>
</div>

---

**Aegis MCP Server** empowers AI assistants (like Claude, Cursor, and GitHub Copilot) to perform cloud architecture administration, security scanning, and network analyses directly from their execution environments. It wraps powerful underlying tools and SDKs into secure, audited MCP tool sets.

---

## 📸 Demo in Action

```text
AI Agent: "Check if any S3 bucket is publicly accessible"

Tool call → aws_check_s3_public_access
Result → bucket audit report
```

<p align="center">
  <img src="docs/demo-aegis.gif" width="900"/>
</p>

---

## 🌟 Key Features

- 🚀 **FastMCP Server** — Exposes domain-specific tools for AWS, Kubernetes, security scanning, Git, network analysis, Jenkins, and CI/CD pipelines.
- 🔐 **Flexible Authorization** — JWT-based RBAC for production deployments; automatically disabled for local stdio sessions (Claude Desktop, Agent IDEs).
- 📜 **Structured Audit Logging** — Emits clean JSON audit logs for every invocation, suitable for SIEM integrations.
- 🛠 **Expandable Tooling** — Easily add new integrations. Includes ready-to-use scanners for dependencies, secrets, SSL/TLS certs, Semgrep, Trivy, and more.
- 📦 **Docker Ready** — Containerized deployment using a non-root runtime with built-in health checks.
- 🌐 **ASGI Integration** — FastAPI health endpoint alongside MCP streamable-http transport.

---

## 📐 Architecture

```mermaid
flowchart TD
    Client[MCP Client / AI Agent] -->|Tool Call| AuthZ[Auth & RBAC Layer]

    subgraph aegis-mcp["Aegis MCP Server"]
        AuthZ --> Audit[Audit Logger]
        Audit --> ToolsLayer[Tool Dispatch Layer]
    end

    ToolsLayer --> AWS[AWS SDK]
    ToolsLayer --> K8s[kubectl / K8s SDK]
    ToolsLayer --> Sec[Trivy / Semgrep]
    ToolsLayer --> Net[Nmap / SSL]
    ToolsLayer --> Git[Git CLI]
    ToolsLayer --> Jenkins[Jenkins API]
    ToolsLayer --> CF[Cloudflare API MCP]
```

The server receives MCP tool-call requests over **streamable HTTP** or **stdio** transport. In HTTP mode, each request requires a JWT bearer token for authorization. In stdio mode (local usage), authorization is automatically disabled.

---

## 📂 Repository Structure

```text
aegis-mcp/
│
├── server/
│   ├── main.py
│   ├── health.py
│   ├── auth.py
│   └── tools/
│       ├── aws/
│       ├── cicd/          # Jenkins + pipeline tools
│       ├── kubernetes/
│       ├── security/
│       └── network/
│
├── policies/
├── tests/
├── Dockerfile
└── run_stdio.py
```

---

## 🧰 Available Tools

### Example Tool Invocation

```text
Tool: security_run_trivy_scan

Input:
image=nginx:latest

Output:
CRITICAL: 2
HIGH: 4
MEDIUM: 7
```

### Cloud & DevOps
| Tool | Description |
|------|-------------|
| `aws_list_ec2_instances` | List EC2 instances in a specific AWS region |
| `aws_check_s3_public_access` | Audit S3 buckets for public access settings |
| `k8s_list_pods` | List Kubernetes pods in a given namespace |
| `cicd_pipeline_status` | Fetch CI/CD pipeline execution status |
| `git_recent_commits` | Fetch recent commit history from the active Git repo |

### Jenkins CI/CD
| Tool | Description |
|------|-------------|
| `jenkins_list_jobs` | List all jobs on a Jenkins server |
| `jenkins_get_job_info` | Get detailed info about a specific job (build history, health) |
| `jenkins_create_job` | Create a new Jenkins job from XML config |
| `jenkins_trigger_build` | Trigger a build with optional parameters (JSON) |
| `jenkins_get_build_info` | Get result, duration, and status of a specific build |
| `jenkins_get_build_log` | Fetch console output of a build |
| `jenkins_delete_job` | Delete a Jenkins job |

> [!TIP]
> **Jenkins tools require per-call credentials** — pass `url`, `username`, and `api_token` with each call. No global env vars needed.

### Cloudflare

These tools call [Cloudflare's API MCP server](https://mcp.cloudflare.com/mcp). Pass a Cloudflare API token on each call. The token's own permissions decide what `execute` and `cloudflare_call` can change.

| Tool | Description |
|------|-------------|
| `cloudflare_whoami` | Show the user or account behind the API token |
| `cloudflare_docs` | Search Cloudflare developer documentation |
| `cloudflare_search` | Run JavaScript against the OpenAPI spec to find endpoints |
| `cloudflare_execute` | Run JavaScript that calls `cloudflare.request()` |
| `cloudflare_call` | Call any current or later tool on the Cloudflare MCP server |
| `cloudflare_generate_report` | Generate an 8-page executive PDF & HTML overview report with charts |

`cloudflare_call` is the extension point. A new Cloudflare operation does not need a new Aegis tool: pass the remote tool name and a JSON arguments object. Set `CLOUDFLARE_MCP_URL` only if you are not using `https://mcp.cloudflare.com/mcp`. For one-endpoint tools, point that URL at `https://mcp.cloudflare.com/mcp?codemode=false`.

### Application Security & SAST
| Tool | Description |
|------|-------------|
| `security_semgrep_scan` | Run Semgrep SAST scan on a local directory or file |
| `security_run_trivy_scan` | Run Trivy vulnerability scan on a container image |
| `security_scan_secrets` | Scan files/directories for exposed secrets |
| `security_check_dependencies` | Check dependency files for known CVEs via OSV.dev |

### Network & Infrastructure Security
| Tool | Description |
|------|-------------|
| `k8s_security_audit` | Audit Kubernetes clusters (privileged containers, wildcard RBAC, etc.) |
| `network_port_scan` | TCP port scan to detect exposed services |
| `security_check_ssl_certificate` | Validate SSL/TLS certificate details and expiry |
| `security_check_http_headers` | Audit URLs for security headers (HSTS, CSP, etc.) |

> [!IMPORTANT]
> **SAST (Semgrep scan) works only on Agent IDEs (e.g., Antigravity, Cursor) or Claude Co-work.**
> It does **not** work on Claude Desktop due to Windows subprocess pipe limitations with `semgrep-core.exe`. All other tools (secrets scan, SSL check, port scan, etc.) work on all platforms including Claude Desktop.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.12+**
- **Node.js 18+** (only if you want to run via npm/npx)
- **Semgrep** — `pip install semgrep` (for SAST scanning)
- Optional: AWS CLI / `boto3`, `kubectl`, Trivy (for their respective tools)

### Installation

```bash
git clone https://github.com/raghulvj01/aegis-mcp.git
cd aegis-mcp

# Create virtual environment
python -m venv .venv

# Activate it
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Install via npm (Public Package)

```bash
npm install -g @raghulm/aegis-mcp
# or run without installing globally:
npx -y @raghulm/aegis-mcp
```

On first run, the npm wrapper creates a local Python virtual environment and installs dependencies from `requirements.txt` automatically.

---

## 🤖 Usage with AI Agents

### Agent IDE / Antigravity (Recommended)

Add to your MCP config (e.g., `mcp_config.json`):

```json
{
  "mcpServers": {
    "aegis": {
      "command": "npx",
      "args": ["-y", "@raghulm/aegis-mcp"]
    }
  }
}
```

> ✅ **Local tools work**, including Semgrep SAST and Jenkins. Cloudflare tools also work here once you pass an API token.

### Claude Desktop

Add to `claude_desktop_config.json`:
- **Windows**: `%LOCALAPPDATA%\Packages\Claude_...\LocalCache\Roaming\Claude\`
- **Mac**: `~/Library/Application Support/Claude/`

```json
{
  "mcpServers": {
    "aegis": {
      "command": "npx",
      "args": ["-y", "@raghulm/aegis-mcp"]
    }
  }
}
```

> ⚠️ **Semgrep SAST does not work** on Claude Desktop due to Windows pipe limitations. The other local tools do. Cloudflare tools work once you pass an API token.

### Cursor / Windsurf (HTTP Mode)

Start the server, then add to `.cursor/mcp.json`:

```bash
uvicorn server.health:app --host 0.0.0.0 --port 8000
```

```json
{
  "mcpServers": {
    "aegis": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### Docker Deployment

```bash
docker build -t aegis-mcp .
docker run -p 8000:8000 aegis-mcp
```

---

## ⚙️ Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_AUTH_DISABLED` | Disable JWT auth (auto-set for stdio) | `false` |
| `MCP_SERVICE_NAME` | Name of the MCP service | `aegis` |
| `MCP_ENV` | Environment (`dev`, `staging`, `prod`) | `dev` |
| `MCP_ROLES_FILE` | Path to roles policy YAML | `policies/roles.yaml` |
| `MCP_SCOPES_FILE` | Path to scopes policy YAML | `policies/scope_rules.yaml` |
| `OIDC_ISSUER` | Expected JWT `iss` claim | *None* |
| `OIDC_AUDIENCE` | Expected JWT `aud` claim | *None* |

---

## 🗝 Access Control

In **HTTP mode**, every tool requires a `token` argument containing a JWT. The authorization layer checks roles and scopes defined in `policies/roles.yaml` and `policies/scope_rules.yaml`.

In **stdio mode** (local usage via `run_stdio.py`), authorization is **automatically disabled** — no token required.

### Policy Example (`policies/roles.yaml`)

```yaml
roles:
  viewer:
    - aws_list_ec2_instances
    - k8s_list_pods
  security:
    - security_run_trivy_scan
    - security_semgrep_scan
  admin:
    - aws_list_ec2_instances
    - k8s_list_pods
    - security_run_trivy_scan
    - security_semgrep_scan
    # ... all tools
```

---

## 📝 Audit Logging

The `@audit_tool_call` decorator emits structured JSON logs for every invocation:

```json
{
  "timestamp": "2026-03-06T08:00:01+00:00",
  "level": "INFO",
  "event": "tool_call_succeeded",
  "tool": "security_run_trivy_scan",
  "duration_ms": 1204
}
```

---

## 🛡️ Security Best Practices

1. **Enforce JWT Signature Validation** — Update `server/auth.py` to verify RS256 JWTs using your IdP's JWKS endpoint for production.
2. **Least-Privilege Credentials** — Assign ReadOnly IAM / K8s roles to the server environment.
3. **Monitor Audit Logs** — Forward JSON logs to a SIEM. Set up anomaly detection for aggressive looping.

---

## 🛣️ Roadmap

- [x] Jenkins CI/CD integration (list, create, trigger, inspect, delete jobs) ✅
- [ ] Terraform security scanner
- [ ] IAM policy risk detection
- [ ] Kubernetes misconfiguration scanner (Basic `k8s_security_audit` implemented!)
- [ ] GitHub Actions security audit
- [ ] Cloud cost analysis tools

---

## 🤝 Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution and maintainer release workflows.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.