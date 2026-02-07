# Resilix Technical Specification

## The Autonomous Site Reliability Engineer

**Version:** 1.1  
**Status:** Technical Specification  
**Target:** Gemini 3 Hackathon (Deadline: Feb 9, 2026)  
**Tech Stack:** Python 3.12, Google ADK, Gemini 3 Flash, MCP (Atlassian + GitHub), Prometheus, Vite/React (Frontend), Cloud Run/Users/taahirsuleman/Documents/TechSpec.md

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Hackathon Alignment](#2-hackathon-alignment)
3. [System Architecture](#3-system-architecture)
4. [Agent Specifications](#4-agent-specifications)
5. [Gemini 3 Feature Utilization](#5-gemini-3-feature-utilization)
6. [MCP Integration](#6-mcp-integration)
7. [State Management](#7-state-management)
8. [Tool Definitions](#8-tool-definitions)
9. [API Design](#9-api-design)
10. [Data Models](#10-data-models)
11. [Project Structure](#11-project-structure)
12. [Deployment Architecture](#12-deployment-architecture)
13. [Testing Strategy](#13-testing-strategy)
14. [Demo Strategy](#14-demo-strategy)
15. [Implementation Phases](#15-implementation-phases)
16. [Frontend Architecture](#16-frontend-architecture)

---

## 1. Executive Summary

Resilix is an autonomous multi-agent system that acts as an "Autonomous SRE" - detecting, diagnosing, and fixing production incidents without human intervention. Built on Google ADK and Gemini 3, it transforms incident response from a human emergency into a managed, autonomous background process.

### Core Value Proposition

| Metric | Before Resilix | With Resilix |
|--------|---------------|--------------|
| MTTR (Mean Time to Remediation) | 30-60 minutes | < 60 seconds |
| Human Intervention Required | Always | Only for review |
| 3 AM PagerDuty Alerts | Every incident | Zero (auto-resolved) |
| Audit Trail | Manual documentation | Automatic (Jira + Git) |

---

## 2. Hackathon Alignment

### 2.1 Judging Criteria Optimization

| Criteria | Weight | Resilix Strategy |
|----------|--------|------------------|
| **Technical Execution** | 40% | Multi-agent orchestration with ADK, advanced Gemini 3 features (thinking levels, thought signatures, function calling), MCP integrations |
| **Innovation/Wow Factor** | 30% | First autonomous SRE that doesn't just alert but fixes incidents end-to-end with full audit trail |
| **Potential Impact** | 20% | $16,700/min downtime savings, addresses real enterprise pain (3 AM PagerDuty nightmare) |
| **Presentation/Demo** | 10% | Live demo showing full incident lifecycle: error → detection → diagnosis → Jira ticket → PR → merge → recovery |

### 2.2 Strategic Track Alignment: "The Marathon Agent"

Resilix perfectly aligns with this track:

- **Autonomous systems for long-running tasks**: Continuous monitoring and incident response
- **Thought Signatures for continuity**: Pass investigation context between agents without hallucination
- **Self-correction without human supervision**: CodeMender-style fix validation before deployment

### 2.3 What We Explicitly Avoid

| Discouraged Type | How Resilix Differs |
|-----------------|---------------------|
| Baseline RAG | Uses agentic reasoning with tool calls, not simple retrieval |
| Prompt-only wrappers | Multi-step orchestration with 4 specialized agents |
| Generic chatbots | Domain-specific SRE system with real integrations |
| Single-prompt solutions | Complex workflow spanning logs → RCA → Jira → GitHub → deployment |

---

## 3. System Architecture

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNAL SYSTEMS                                  │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────┤
│   Prometheus    │     GitHub      │      Jira       │   Cloud Logging      │
│   Alertmanager  │   Repository    │     Cloud       │   / ELK Stack        │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬───────────┘
         │                 │                 │                   │
         │ Webhook         │ MCP             │ MCP               │ API
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RESILIX MICROSERVICE                                 │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                        Webhook Handler (FastAPI)                       │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
│                                      │                                       │
│  ┌───────────────────────────────────▼───────────────────────────────────┐  │
│  │                    ORCHESTRATOR (SequentialAgent)                      │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐   │  │
│  │  │  SENTINEL   │→ │  SHERLOCK   │→ │      PARALLEL AGENT         │   │  │
│  │  │  (Observer) │  │(Investigator)│  │  ┌───────┐  ┌───────────┐  │   │  │
│  │  │             │  │             │  │  │ ADMIN │  │ MECHANIC  │  │   │  │
│  │  │ Flash/Low   │  │ Pro/High    │  │  │(Jira) │  │ (GitHub)  │  │   │  │
│  │  └─────────────┘  └─────────────┘  │  └───────┘  └───────────┘  │   │  │
│  │                                     └─────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                      │                                       │
│  ┌───────────────────────────────────▼───────────────────────────────────┐  │
│  │                     Session State Manager (Redis)                      │  │
│  │         validated_alert | thought_signature | jira_ticket | result    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Agent Orchestration Pattern

```python
# Root architecture using Google ADK patterns
from google.adk.agents import SequentialAgent, ParallelAgent, LlmAgent

# The main orchestration flow
root_agent = SequentialAgent(
    name="ResilixOrchestrator",
    description="Orchestrates the autonomous incident response workflow",
    sub_agents=[
        sentinel_agent,       # Step 1: Validate and enrich alert
        sherlock_agent,       # Step 2: Perform RCA with deep reasoning
        ParallelAgent(        # Step 3: Parallel remediation actions
            name="RemediationSwarm",
            description="Executes remediation actions in parallel",
            sub_agents=[
                administrator_agent,  # Creates Jira ticket
                mechanic_agent        # Generates and deploys fix
            ]
        )
    ]
)
```

### 3.3 Data Flow Sequence

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│Prometheus│    │ Sentinel │    │ Sherlock │    │  Admin   │    │ Mechanic │
└────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘
     │               │               │               │               │
     │ Alert JSON    │               │               │               │
     │──────────────>│               │               │               │
     │               │               │               │               │
     │               │ Validate &    │               │               │
     │               │ Enrich        │               │               │
     │               │───────────────>               │               │
     │               │               │               │               │
     │               │               │ Query Logs    │               │
     │               │               │ Get Traces    │               │
     │               │               │ Get Deploys   │               │
     │               │               │               │               │
     │               │               │ Thought       │               │
     │               │               │ Signature     │               │
     │               │               │───────────────>               │
     │               │               │               │               │
     │               │               │               │ Create Ticket │
     │               │               │               │──────────────>│
     │               │               │               │               │
     │               │               │───────────────────────────────>
     │               │               │               │               │
     │               │               │               │  Clone Repo   │
     │               │               │               │  Generate Fix │
     │               │               │               │  Validate     │
     │               │               │               │  Create PR    │
     │               │               │               │  Merge        │
     │               │               │               │               │
     │<──────────────────────────────────────────────────────────────│
     │               │               │               │    RESOLVED   │
```

---

## 4. Agent Specifications

### 4.0 Hybrid Architecture Philosophy

> **Key Principle**: Put detection thresholds, dedupe, maintenance windows, ticket formatting, and PR policy in code. Keep LLM use for RCA synthesis and patch proposal only.

Resilix uses a **hybrid agent architecture** with 4 named roles but only 2 reasoning-heavy LLM agents:

| Agent | Type | Model | LLM Usage |
|-------|------|-------|-----------|
| **Sentinel** | Deterministic + Light LLM | Flash (fallback only) | Classification only if ambiguous |
| **Sherlock** | Full LLM Agent | Flash (high thinking) | RCA synthesis |
| **Administrator** | Deterministic Service | None | Template-based ticket creation |
| **Mechanic** | LLM Agent + Tools | Flash (high thinking) | Patch proposal |

**Why This Architecture?**

1. **Lower implementation risk**: Deterministic agents are more reliable than LLM-powered ones
2. **Better reliability**: Business logic stays in code/services, not prompts
3. **Hackathon-friendly**: Multi-agent narrative for demo while keeping complexity manageable
4. **Cost efficient**: Minimal LLM calls where deterministic logic suffices

**Model Decision: Gemini 3 Flash Only**

> **IMPORTANT**: All LLM-powered components use `gemini-3-flash` exclusively. We do NOT use `gemini-3-pro`.

Rationale:
- **Cost efficiency**: Flash is significantly cheaper for hackathon budget
- **Latency**: Flash provides faster responses, critical for real-time incident response
- **Sufficient capability**: Flash with `thinking_level="high"` provides adequate reasoning for RCA and code generation
- **Simplicity**: Single model simplifies configuration and deployment



### 4.5 Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RESILIX AGENT ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐ │
│  │    SENTINEL     │    │    SHERLOCK     │    │    PARALLEL EXECUTION   │ │
│  │  (Deterministic)│───>│   (LLM Agent)   │───>│                         │ │
│  │                 │    │                 │    │  ┌───────────────────┐  │ │
│  │  • Thresholds   │    │  • Flash Model  │    │  │   ADMINISTRATOR   │  │ │
│  │  • Dedup        │    │  • High Think   │    │  │  (Deterministic)  │  │ │
│  │  • Maintenance  │    │  • RCA Tools    │    │  │  • Jira Templates │  │ │
│  │  • LLM Fallback │    │  • Evidence     │    │  └───────────────────┘  │ │
│  └─────────────────┘    └─────────────────┘    │                         │ │
│                                                 │  ┌───────────────────┐  │ │
│                                                 │  │     MECHANIC      │  │ │
│                                                 │  │   (LLM Agent)     │  │ │
│                                                 │  │  • Flash Model    │  │ │
│                                                 │  │  • High Think     │  │ │
│                                                 │  │  • GitHub Tools   │  │ │
│                                                 │  └───────────────────┘  │ │
│                                                 └─────────────────────────┘ │
│                                                                              │
│  LLM Calls: 2 (Sherlock + Mechanic)    Deterministic: 2 (Sentinel + Admin) │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Gemini 3 Feature Utilization

### 5.1 Model Configuration

> **Single Model Strategy**: All LLM operations use `gemini-3-flash` exclusively.

```python
# config/settings.py
class Settings(BaseSettings):
    # Single model for all LLM agents
    gemini_model: str = "gemini-3-flash"
    
    # Thinking levels vary by agent role
    sherlock_thinking_level: str = "high"   # Deep RCA reasoning
    mechanic_thinking_level: str = "high"   # Careful code generation
    
    # Feature flags
    include_thoughts: bool = True  # Audit trail for LLM reasoning
```

### 5.2 Feature Mapping

| Gemini 3 Feature | Agent | Implementation | Hackathon Value |
|-----------------|-------|----------------|-----------------|
| **Thinking Level: High** | Sherlock, Mechanic | Deep reasoning for RCA and code | Marathon Agent track |
| **include_thoughts=True** | Sherlock, Mechanic | Audit trail of reasoning | Transparency |
| **Function Calling** | Sherlock, Mechanic | Tool integration | Technical execution |
| **Structured Output** | All components | Pydantic schemas | Type safety |
| **1M Token Context** | Sherlock | Full log file analysis | Advanced capability |
| **Code Generation** | Mechanic | Generate patches | Fix automation |

### 5.3 Thinking Configuration

```python
from google.genai import types

# Sherlock: Deep investigation reasoning
sherlock_config = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(
        thinking_level="high",      # Multi-step RCA reasoning
        include_thoughts=True       # Capture for audit trail
    ),
    temperature=0.7  # Allow hypothesis exploration
)

# Mechanic: Careful code generation
mechanic_config = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(
        thinking_level="high",      # Careful analysis for fixes
        include_thoughts=True       # Capture for audit trail
    ),
    temperature=0.2  # Very deterministic for code
)
```

### 5.4 Why Flash Over Pro

| Factor | Flash | Pro |
|--------|-------|-----|
| **Cost** | ~10x cheaper | More expensive |
| **Latency** | ~2x faster | Slower |
| **Reasoning** | Sufficient with high thinking | Better but overkill |
| **Context Window** | 1M tokens | 1M tokens |
| **For Resilix** | Ideal for real-time SRE | Unnecessary complexity |

> **Key Insight**: Gemini 3 Flash with `thinking_level="high"` provides the reasoning depth needed for root cause analysis and code generation, at a fraction of the cost and latency of Pro.

### 5.3 Thought Signature Implementation

Thought Signatures ensure context continuity across agent handoffs:

```python
# In Sherlock's output processing
def process_sherlock_output(response, session_state):
    """Extract and validate thought signature from Sherlock's response"""
    
    # Parse structured output
    thought_signature = ThoughtSignature.model_validate(
        response.structured_content
    )
    
    # Capture the reasoning chain for audit
    reasoning_chain = []
    for part in response.candidates[0].content.parts:
        if part.thought:
            reasoning_chain.append({
                "type": "reasoning",
                "content": part.text,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    # Attach reasoning to thought signature
    thought_signature_with_reasoning = {
        **thought_signature.model_dump(),
        "reasoning_chain": reasoning_chain,
        "gemini_thoughts_token_count": response.usage_metadata.thoughts_token_count
    }
    
    # Store in session state for downstream agents
    session_state["thought_signature"] = thought_signature_with_reasoning
    
    return thought_signature
```

---

## 6. MCP Integration

### 6.1 Atlassian MCP (mcp-atlassian)

**Package**: `mcp-atlassian` (sooperset/mcp-atlassian)  
**Transport**: stdio  
**Authentication**: API Token

```python
# MCP Atlassian Integration Setup
import os
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Atlassian MCP Server configuration
atlassian_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uvx",
            args=["mcp-atlassian"],
            env={
                "JIRA_URL": os.environ["JIRA_URL"],
                "JIRA_USERNAME": os.environ["JIRA_USERNAME"],
                "JIRA_API_TOKEN": os.environ["JIRA_API_TOKEN"],
            }
        )
    )
)

# Available Jira Tools from mcp-atlassian:
# - jira_search: Search issues with JQL
# - jira_get_issue: Get issue details
# - jira_create_issue: Create new issue
# - jira_update_issue: Update existing issue
# - jira_transition_issue: Change issue status
# - jira_add_comment: Add comment to issue
```

**Jira Ticket Creation Flow**:
```python
async def create_incident_ticket(thought_signature: ThoughtSignature) -> dict:
    """Create a Jira ticket from the investigation results"""
    
    # Map severity to Jira priority
    priority_map = {
        "critical": "Highest",
        "high": "High", 
        "medium": "Medium",
        "low": "Low"
    }
    
    # Build description from thought signature
    description = f"""
    h2. Incident Summary
    {thought_signature.investigation_summary}
    
    h2. Root Cause
    *Category:* {thought_signature.root_cause_category}
    *Description:* {thought_signature.root_cause}
    *Confidence:* {thought_signature.confidence_score * 100:.1f}%
    
    h2. Affected Services
    {', '.join(thought_signature.affected_services)}
    
    h2. Evidence Chain
    {format_evidence_chain(thought_signature.evidence_chain)}
    
    h2. Recommended Action
    {thought_signature.recommended_action}
    
    h2. Related Commits
    {format_commits(thought_signature.related_commits)}
    
    ----
    _This ticket was automatically created by Resilix._
    _Incident ID: {thought_signature.incident_id}_
    """
    
    # Create the ticket
    result = await jira_create_issue(
        project="SRE",  # Or from config
        issue_type="Bug",
        summary=f"[AUTO] {thought_signature.root_cause_category}: {thought_signature.root_cause[:50]}",
        description=description,
        priority=priority_map.get(thought_signature.severity, "Medium"),
        labels=["resilix-auto", "incident", thought_signature.affected_services[0]]
    )
    
    return result
```

### 6.2 GitHub MCP Server

**Package**: `ghcr.io/github/github-mcp-server` (Docker) or binary  
**Transport**: stdio  
**Authentication**: Personal Access Token (PAT)

```python
# GitHub MCP Server configuration
github_mcp = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="docker",
            args=[
                "run", "-i", "--rm",
                "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                "ghcr.io/github/github-mcp-server"
            ],
            env={
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_TOKEN"]
            }
        )
    )
)

# Key GitHub Tools Used:
# - get_file_contents: Read repository files
# - search_code: Find code patterns
# - create_branch: Create fix branch
# - push_files: Push the fix
# - create_pull_request: Open PR
# - merge_pull_request: Merge when CI passes
# - list_commits: Check recent changes
```

**GitHub Remediation Flow**:
```python
async def apply_code_fix(thought_signature: ThoughtSignature, fix_code: str) -> dict:
    """Apply a code fix via GitHub MCP"""
    
    owner, repo = thought_signature.target_repository.split("/")
    incident_id = thought_signature.incident_id
    
    # Step 1: Create branch
    branch_name = f"fix/resilix-{incident_id}"
    await github_create_branch(
        owner=owner,
        repo=repo,
        branch=branch_name,
        from_branch="main"
    )
    
    # Step 2: Push the fix
    await github_push_files(
        owner=owner,
        repo=repo,
        branch=branch_name,
        files=[{
            "path": thought_signature.target_file,
            "content": fix_code
        }],
        message=f"fix: {thought_signature.root_cause[:50]}\n\nIncident: {incident_id}\nAuto-generated by Resilix"
    )
    
    # Step 3: Create PR
    pr_result = await github_create_pull_request(
        owner=owner,
        repo=repo,
        title=f"[Resilix] Fix: {thought_signature.root_cause[:50]}",
        body=f"""
## Automated Fix by Resilix

**Incident ID:** {incident_id}
**Root Cause:** {thought_signature.root_cause}
**Confidence:** {thought_signature.confidence_score * 100:.1f}%

### Changes
This PR fixes the issue identified by automated root cause analysis.

### Evidence
{thought_signature.investigation_summary}

### Jira Ticket
Link to be added by Administrator agent.

---
_This PR was automatically generated by Resilix._
        """,
        head=branch_name,
        base="main"
    )
    
    # Step 4: Wait for CI and merge (MVP: auto-merge if CI passes)
    # In production, this would poll CI status
    pr_number = pr_result["number"]
    
    # For MVP, attempt merge after short delay
    await asyncio.sleep(30)  # Wait for CI
    
    merge_result = await github_merge_pull_request(
        owner=owner,
        repo=repo,
        pullNumber=pr_number,
        merge_method="squash"
    )
    
    return {
        "branch": branch_name,
        "pr_number": pr_number,
        "pr_url": pr_result["html_url"],
        "merged": merge_result.get("merged", False)
    }
```

### 6.3 MCP Connection Lifecycle

```python
from contextlib import asynccontextmanager
from google.adk.agents import LlmAgent

@asynccontextmanager
async def mcp_connections():
    """Manage MCP server connections lifecycle"""
    
    # Initialize connections
    atlassian_tools = await atlassian_mcp.initialize()
    github_tools = await github_mcp.initialize()
    
    try:
        yield {
            "atlassian": atlassian_tools,
            "github": github_tools
        }
    finally:
        # Cleanup connections
        await atlassian_mcp.cleanup()
        await github_mcp.cleanup()
```

---

## 7. State Management

### 7.1 Session State Schema

```python
# State keys used across agents
STATE_SCHEMA = {
    # Alert processing
    "raw_alert": "Original Prometheus alert payload",
    "validated_alert": "Sentinel's validated and enriched alert",
    
    # Investigation
    "thought_signature": "Sherlock's complete RCA result",
    "investigation_logs": "All logs queried during investigation",
    
    # Remediation
    "jira_ticket": "Created Jira ticket details",
    "remediation_result": "Mechanic's deployment result",
    
    # Audit
    "incident_timeline": "Chronological event log",
    "agent_execution_times": "Performance metrics per agent"
}
```

### 7.2 State Flow Between Agents

```python
from google.adk.agents import SequentialAgent
from dataclasses import dataclass

@dataclass
class IncidentState:
    """Type-safe state container for incident processing"""
    raw_alert: dict
    validated_alert: Optional[ValidatedAlert] = None
    thought_signature: Optional[ThoughtSignature] = None
    jira_ticket: Optional[JiraTicketResult] = None
    remediation_result: Optional[RemediationResult] = None
    timeline: List[TimelineEvent] = field(default_factory=list)

# ADK handles state via output_key
# Each agent reads from state and writes via output_key

# Sentinel writes: state["validated_alert"]
# Sherlock reads: state["validated_alert"], writes: state["thought_signature"]
# Admin reads: state["thought_signature"], writes: state["jira_ticket"]
# Mechanic reads: state["thought_signature"], writes: state["remediation_result"]
```

### 7.3 Session Persistence

```python
from google.adk.sessions import DatabaseSessionService

# For production: PostgreSQL persistence
session_service = DatabaseSessionService(
    connection_string=os.environ["DATABASE_URL"]
)

# For development: In-memory
from google.adk.sessions import InMemorySessionService
session_service = InMemorySessionService()
```

---

## 8. Tool Definitions

### 8.1 Custom Tools

```python
from google.adk.tools import tool

@tool
def query_logs(
    service_name: str,
    time_range_minutes: int = 30,
    log_level: str = "ERROR",
    search_pattern: Optional[str] = None
) -> dict:
    """Query application logs for errors and exceptions.
    
    Args:
        service_name: Name of the service to query logs for
        time_range_minutes: How far back to search (default 30)
        log_level: Minimum log level (ERROR, WARN, INFO)
        search_pattern: Optional regex pattern to filter logs
    
    Returns:
        dict with log entries, count, and time range
    """
    # Implementation calls Cloud Logging / ELK API
    from services.logging_client import LoggingClient
    
    client = LoggingClient()
    logs = client.query(
        service=service_name,
        minutes=time_range_minutes,
        level=log_level,
        pattern=search_pattern
    )
    
    return {
        "service": service_name,
        "log_count": len(logs),
        "time_range": f"last {time_range_minutes} minutes",
        "entries": logs[:100],  # Limit for context window
        "has_more": len(logs) > 100
    }

@tool
def get_recent_deployments(
    service_name: str,
    hours: int = 24
) -> dict:
    """Get recent deployments that might have caused the issue.
    
    Args:
        service_name: Service to check deployments for
        hours: How far back to look (default 24)
    
    Returns:
        List of deployments with commit info and timestamps
    """
    # Implementation queries deployment system
    from services.deployment_client import DeploymentClient
    
    client = DeploymentClient()
    deployments = client.get_recent(service=service_name, hours=hours)
    
    return {
        "service": service_name,
        "deployment_count": len(deployments),
        "deployments": [
            {
                "commit_sha": d.commit_sha,
                "author": d.author,
                "message": d.message,
                "deployed_at": d.deployed_at.isoformat(),
                "environment": d.environment
            }
            for d in deployments
        ]
    }

@tool
def validate_code(
    code: str,
    language: str = "python",
    file_path: Optional[str] = None
) -> dict:
    """Validate generated code for syntax and basic correctness.
    
    Args:
        code: The code to validate
        language: Programming language (python, javascript, etc.)
        file_path: Original file path for context
    
    Returns:
        Validation result with any errors found
    """
    import ast
    import subprocess
    
    result = {"valid": True, "errors": [], "warnings": []}
    
    if language == "python":
        try:
            ast.parse(code)
        except SyntaxError as e:
            result["valid"] = False
            result["errors"].append({
                "type": "syntax_error",
                "line": e.lineno,
                "message": str(e)
            })
        
        # Run ruff for linting
        try:
            proc = subprocess.run(
                ["ruff", "check", "--stdin-filename", file_path or "code.py"],
                input=code.encode(),
                capture_output=True
            )
            if proc.returncode != 0:
                result["warnings"].extend(
                    proc.stdout.decode().strip().split("\n")
                )
        except FileNotFoundError:
            pass  # ruff not installed
    
    return result

@tool
def get_service_dependencies(service_name: str) -> dict:
    """Get upstream and downstream dependencies for a service.
    
    Args:
        service_name: Service to analyze
    
    Returns:
        Dependency graph with health status
    """
    from services.topology_client import TopologyClient
    
    client = TopologyClient()
    deps = client.get_dependencies(service_name)
    
    return {
        "service": service_name,
        "upstream": deps.upstream,
        "downstream": deps.downstream,
        "critical_path": deps.critical_path
    }

@tool  
def check_maintenance_window(service_name: str) -> dict:
    """Check if service is in a maintenance window.
    
    Args:
        service_name: Service to check
    
    Returns:
        Maintenance window status
    """
    from services.maintenance_client import MaintenanceClient
    
    client = MaintenanceClient()
    window = client.get_active_window(service_name)
    
    return {
        "in_maintenance": window is not None,
        "window": window.model_dump() if window else None
    }
```

### 8.2 Tool Registration

```python
from google.adk.agents import LlmAgent

# Register tools with agents
sentinel_tools = [
    validate_alert_tool,
    check_maintenance_window,
    enrich_context_tool
]

sherlock_tools = [
    query_logs,
    get_recent_deployments,
    get_service_dependencies,
    get_distributed_traces,
    get_service_metrics
]

admin_tools = [
    # From Atlassian MCP
    *atlassian_mcp.get_tools()
]

mechanic_tools = [
    # From GitHub MCP
    *github_mcp.get_tools(),
    # Custom validation
    validate_code
]
```

---

## 9. API Design

### 9.1 Webhook Endpoint

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
import uuid

app = FastAPI(title="Resilix API", version="1.0.0")

class PrometheusAlert(BaseModel):
    """Prometheus AlertManager webhook payload"""
    status: str  # "firing" or "resolved"
    labels: dict
    annotations: dict
    startsAt: str
    endsAt: Optional[str]
    generatorURL: Optional[str]

class AlertWebhook(BaseModel):
    """Full AlertManager webhook"""
    version: str
    groupKey: str
    status: str
    receiver: str
    alerts: List[PrometheusAlert]

@app.post("/webhook/prometheus")
async def handle_prometheus_alert(
    webhook: AlertWebhook,
    background_tasks: BackgroundTasks
):
    """Receive Prometheus AlertManager webhooks and trigger incident response."""
    
    # Only process firing alerts
    firing_alerts = [a for a in webhook.alerts if a.status == "firing"]
    
    if not firing_alerts:
        return {"status": "ignored", "reason": "no firing alerts"}
    
    # Create incident ID
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    
    # Process in background
    background_tasks.add_task(
        process_incident,
        incident_id=incident_id,
        alerts=firing_alerts
    )
    
    return {
        "status": "accepted",
        "incident_id": incident_id,
        "alerts_count": len(firing_alerts)
    }

async def process_incident(incident_id: str, alerts: List[PrometheusAlert]):
    """Background task to process incident through agent swarm."""
    from google.adk.runners import Runner
    
    # Create session for this incident
    session = await session_service.create_session(
        app_name="resilix",
        user_id="prometheus",
        session_id=incident_id
    )
    
    # Initialize session state
    session.state["raw_alert"] = [a.model_dump() for a in alerts]
    session.state["incident_id"] = incident_id
    session.state["timeline"] = [{
        "event": "incident_created",
        "timestamp": datetime.utcnow().isoformat()
    }]
    
    # Run the agent swarm
    runner = Runner(
        agent=root_agent,
        session_service=session_service
    )
    
    try:
        result = await runner.run_async(
            session=session,
            input_message=json.dumps(alerts[0].model_dump())
        )
        
        # Update session with final result
        session.state["status"] = "resolved"
        session.state["timeline"].append({
            "event": "incident_resolved",
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        session.state["status"] = "failed"
        session.state["error"] = str(e)
        raise
```

### 9.2 API Contract Summary

| Endpoint | Method | Purpose | Frontend Use |
|----------|--------|---------|--------------|
| `/webhook/prometheus` | POST | Receive alerts from Prometheus | Backend only |
| `/incidents` | GET | List all incidents | Incident feed |
| `/incidents/{id}` | GET | Get incident detail | Detail view |
| `/incidents/{id}/approve-merge` | POST | Approve PR merge | Approval button |
| `/health` | GET | Health check | Monitoring |

### 9.3 Status Endpoints

```python
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class PRStatus(str, Enum):
    NOT_CREATED = "not_created"
    PENDING_CI = "pending_ci"
    CI_PASSED = "ci_passed"
    CI_FAILED = "ci_failed"
    MERGED = "merged"

class TimelineEvent(BaseModel):
    """Structured timeline event for UI display"""
    event: str  # alert_received, rca_complete, jira_created, pr_created, etc.
    timestamp: datetime
    description: Optional[str] = None
    metadata: Optional[dict] = None

class IncidentDetailResponse(BaseModel):
    """Full incident response for detail view"""
    incident_id: str
    status: str  # processing, awaiting_approval, resolved, failed
    severity: str
    service_name: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    mttr_seconds: Optional[float] = None
    
    # Approval gate
    approval_status: ApprovalStatus
    pr_status: PRStatus
    
    # Details
    validated_alert: Optional[dict] = None
    thought_signature: Optional[dict] = None
    jira_ticket: Optional[dict] = None
    remediation_result: Optional[dict] = None
    
    # Structured timeline for UI
    timeline: List[TimelineEvent]

class IncidentSummary(BaseModel):
    """Summary for incident feed list"""
    incident_id: str
    status: str
    severity: str
    service_name: str
    created_at: datetime
    mttr_seconds: Optional[float] = None
    approval_status: ApprovalStatus
    pr_status: PRStatus

@app.get("/incidents/{incident_id}", response_model=IncidentDetailResponse)
async def get_incident_status(incident_id: str):
    """Get current status of incident remediation."""
    
    session = await session_service.get_session(
        app_name="resilix",
        session_id=incident_id
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    state = session.state
    timeline_raw = state.get("timeline", [])
    
    # Convert raw timeline to structured events
    timeline = [
        TimelineEvent(
            event=t.get("event"),
            timestamp=datetime.fromisoformat(t.get("timestamp")),
            description=t.get("description"),
            metadata=t.get("metadata")
        )
        for t in timeline_raw
    ]
    
    # Calculate MTTR if resolved
    mttr_seconds = None
    if state.get("status") == "resolved" and len(timeline) >= 2:
        start = timeline[0].timestamp
        end = timeline[-1].timestamp
        mttr_seconds = (end - start).total_seconds()
    
    return IncidentDetailResponse(
        incident_id=incident_id,
        status=state.get("status", "processing"),
        severity=state.get("validated_alert", {}).get("severity", "medium"),
        service_name=state.get("validated_alert", {}).get("service_name", "unknown"),
        created_at=timeline[0].timestamp if timeline else datetime.utcnow(),
        resolved_at=timeline[-1].timestamp if state.get("status") == "resolved" else None,
        mttr_seconds=mttr_seconds,
        approval_status=ApprovalStatus(state.get("approval_status", "not_required")),
        pr_status=PRStatus(state.get("pr_status", "not_created")),
        validated_alert=state.get("validated_alert"),
        thought_signature=state.get("thought_signature"),
        jira_ticket=state.get("jira_ticket"),
        remediation_result=state.get("remediation_result"),
        timeline=timeline
    )

@app.get("/incidents")
async def list_incidents(
    status: Optional[str] = None,
    limit: int = 50
) -> dict:
    """List recent incidents for the incident feed."""
    
    incidents = await session_service.list_sessions(
        app_name="resilix",
        limit=limit
    )
    
    summaries = []
    for s in incidents:
        state = s.state
        timeline = state.get("timeline", [])
        
        # Calculate MTTR if resolved
        mttr_seconds = None
        if state.get("status") == "resolved" and len(timeline) >= 2:
            start = datetime.fromisoformat(timeline[0].get("timestamp"))
            end = datetime.fromisoformat(timeline[-1].get("timestamp"))
            mttr_seconds = (end - start).total_seconds()
        
        summaries.append(IncidentSummary(
            incident_id=s.id,
            status=state.get("status", "processing"),
            severity=state.get("validated_alert", {}).get("severity", "medium"),
            service_name=state.get("validated_alert", {}).get("service_name", "unknown"),
            created_at=datetime.fromisoformat(timeline[0].get("timestamp")) if timeline else datetime.utcnow(),
            mttr_seconds=mttr_seconds,
            approval_status=ApprovalStatus(state.get("approval_status", "not_required")),
            pr_status=PRStatus(state.get("pr_status", "not_created")),
        ))
    
    # Filter by status if provided
    if status:
        summaries = [s for s in summaries if s.status == status]
    
    return {"incidents": summaries}
```

### 9.4 Approve Merge Endpoint

```python
@app.post("/incidents/{incident_id}/approve-merge")
async def approve_merge(incident_id: str) -> dict:
    """Approve the pending PR merge for an incident.
    
    This is the ONLY write action exposed to the frontend.
    Triggers the Mechanic to merge the PR after approval.
    
    Prerequisites:
    - Incident must exist
    - PR must be created (pr_status != "not_created")
    - CI must have passed (pr_status == "ci_passed")
    - Must not already be approved/merged
    """
    
    session = await session_service.get_session(
        app_name="resilix",
        session_id=incident_id
    )
    
    if not session:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    state = session.state
    
    # Validate current state
    current_pr_status = state.get("pr_status", "not_created")
    current_approval = state.get("approval_status", "not_required")
    
    if current_pr_status == "not_created":
        raise HTTPException(
            status_code=400, 
            detail="No PR exists for this incident"
        )
    
    if current_pr_status == "merged":
        raise HTTPException(
            status_code=400, 
            detail="PR has already been merged"
        )
    
    if current_pr_status != "ci_passed":
        raise HTTPException(
            status_code=400, 
            detail=f"CI has not passed. Current status: {current_pr_status}"
        )
    
    if current_approval == "approved":
        raise HTTPException(
            status_code=400, 
            detail="Merge has already been approved"
        )
    
    # Update state
    state["approval_status"] = "approved"
    state["timeline"].append({
        "event": "merge_approved",
        "timestamp": datetime.utcnow().isoformat(),
        "description": "Human operator approved the PR merge"
    })
    
    # Trigger async merge process
    background_tasks.add_task(
        execute_merge,
        incident_id=incident_id,
        pr_url=state.get("remediation_result", {}).get("pr_url")
    )
    
    return {
        "status": "approved",
        "incident_id": incident_id,
        "message": "Merge approved. PR will be merged shortly."
    }

async def execute_merge(incident_id: str, pr_url: str):
    """Background task to execute the PR merge after approval."""
    
    session = await session_service.get_session(
        app_name="resilix",
        session_id=incident_id
    )
    
    try:
        # Call GitHub API to merge the PR
        # (implementation uses GitHub MCP or direct API)
        await github_service.merge_pr(pr_url)
        
        # Update state
        session.state["pr_status"] = "merged"
        session.state["status"] = "resolved"
        session.state["timeline"].append({
            "event": "pr_merged",
            "timestamp": datetime.utcnow().isoformat(),
            "description": "PR successfully merged"
        })
        session.state["timeline"].append({
            "event": "incident_resolved",
            "timestamp": datetime.utcnow().isoformat(),
            "description": "Incident automatically resolved after successful merge"
        })
        
    except Exception as e:
        session.state["timeline"].append({
            "event": "merge_failed",
            "timestamp": datetime.utcnow().isoformat(),
            "description": f"Merge failed: {str(e)}"
        })
        raise
```

### 9.5 Health Check

```python
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": "1.1.0",
        "model": "gemini-3-flash",
        "agents": {
            "sentinel": "deterministic",
            "sherlock": "llm",
            "administrator": "deterministic", 
            "mechanic": "llm"
        }
    }
```

---

## 10. Data Models

### 10.1 Complete Model Definitions

```python
# models/alert.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class AlertStatus(str, Enum):
    FIRING = "firing"
    RESOLVED = "resolved"

class ValidatedAlert(BaseModel):
    """Output from Sentinel Agent"""
    alert_id: str
    is_actionable: bool
    severity: Severity
    service_name: str
    error_type: str
    error_rate: float
    affected_endpoints: List[str]
    triggered_at: datetime
    enrichment: Dict[str, Any]
    triage_reason: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "alert_id": "ALT-123456",
                "is_actionable": True,
                "severity": "high",
                "service_name": "checkout-service",
                "error_type": "NullPointerException",
                "error_rate": 5.2,
                "affected_endpoints": ["/api/checkout", "/api/payment"],
                "triggered_at": "2026-02-02T10:30:00Z",
                "enrichment": {"team": "payments", "tier": "critical"},
                "triage_reason": "Error rate exceeds 2% threshold"
            }
        }


# models/thought_signature.py
class RootCauseCategory(str, Enum):
    CODE_BUG = "code_bug"
    CONFIG_ERROR = "config_error"
    DEPENDENCY_FAILURE = "dependency_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    EXTERNAL_SERVICE = "external_service"

class RecommendedAction(str, Enum):
    FIX_CODE = "fix_code"
    ROLLBACK = "rollback"
    SCALE_UP = "scale_up"
    CONFIG_CHANGE = "config_change"
    ESCALATE_HUMAN = "escalate_human"

class Evidence(BaseModel):
    """Single piece of investigation evidence"""
    source: str = Field(description="logs|traces|metrics|deployment|dependency")
    timestamp: datetime
    content: str
    relevance: str
    confidence: float = Field(ge=0, le=1)

class ThoughtSignature(BaseModel):
    """Complete investigation result from Sherlock Agent"""
    incident_id: str
    
    # Root cause analysis
    root_cause: str
    root_cause_category: RootCauseCategory
    evidence_chain: List[Evidence]
    confidence_score: float = Field(ge=0, le=1)
    
    # Impact assessment  
    affected_services: List[str]
    blast_radius: str = Field(description="limited|moderate|widespread")
    
    # Remediation guidance
    recommended_action: RecommendedAction
    target_repository: Optional[str] = None
    target_file: Optional[str] = None
    target_line: Optional[int] = None
    related_commits: List[str] = []
    fix_description: Optional[str] = None
    
    # Audit trail
    investigation_summary: str
    investigation_duration_seconds: float
    hypotheses_tested: List[str] = []
    
    class Config:
        json_schema_extra = {
            "example": {
                "incident_id": "INC-ABC12345",
                "root_cause": "Missing null check in CheckoutService.processPayment() introduced in commit a1b2c3d",
                "root_cause_category": "code_bug",
                "confidence_score": 0.92,
                "affected_services": ["checkout-service", "payment-service"],
                "blast_radius": "moderate",
                "recommended_action": "fix_code",
                "target_repository": "acme/checkout-service",
                "target_file": "src/services/checkout.py",
                "target_line": 142,
                "related_commits": ["a1b2c3d", "e4f5g6h"]
            }
        }


# models/remediation.py

class ApprovalStatus(str, Enum):
    """Status of human approval for PR merge"""
    NOT_REQUIRED = "not_required"  # Auto-merge allowed (low severity)
    PENDING = "pending"            # Awaiting human approval
    APPROVED = "approved"          # Human approved merge
    REJECTED = "rejected"          # Human rejected merge

class PRStatus(str, Enum):
    """Status of the pull request in the remediation workflow"""
    NOT_CREATED = "not_created"    # No PR exists yet
    PENDING_CI = "pending_ci"      # PR created, CI running
    CI_PASSED = "ci_passed"        # CI passed, ready for merge
    CI_FAILED = "ci_failed"        # CI failed, needs attention
    MERGED = "merged"              # PR successfully merged

class JiraTicketResult(BaseModel):
    """Output from Administrator Service (deterministic)"""
    ticket_key: str  # e.g., "SRE-1234"
    ticket_url: str
    summary: str
    priority: str
    status: str
    created_at: datetime

class RemediationResult(BaseModel):
    """Output from Mechanic Agent"""
    success: bool
    action_taken: RecommendedAction
    
    # Code fix details (if applicable)
    branch_name: Optional[str] = None
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    pr_merged: bool = False
    
    # Rollback details (if applicable)
    rollback_to_commit: Optional[str] = None
    
    # Scaling details (if applicable)
    new_replica_count: Optional[int] = None
    
    # Metadata
    execution_time_seconds: float
    error_message: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "action_taken": "fix_code",
                "branch_name": "fix/resilix-INC-ABC12345",
                "pr_number": 456,
                "pr_url": "https://github.com/acme/checkout-service/pull/456",
                "pr_merged": True,
                "execution_time_seconds": 45.2
            }
        }


# models/incident.py
class IncidentStatus(str, Enum):
    """Status of the overall incident"""
    PROCESSING = "processing"          # Being processed by agents
    AWAITING_APPROVAL = "awaiting_approval"  # PR ready, needs human approval
    MERGING = "merging"                # PR being merged
    RESOLVED = "resolved"              # Incident fully resolved
    FAILED = "failed"                  # Processing failed

class IncidentSummary(BaseModel):
    """Summary for incident feed list view"""
    incident_id: str
    status: IncidentStatus
    severity: Severity
    service_name: str
    created_at: datetime
    mttr_seconds: Optional[float] = None
    approval_status: ApprovalStatus
    pr_status: PRStatus

class IncidentDetailResponse(BaseModel):
    """Full incident response for detail view (API response)"""
    incident_id: str
    status: IncidentStatus
    severity: Severity
    service_name: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    mttr_seconds: Optional[float] = None
    
    # Approval gate status
    approval_status: ApprovalStatus
    pr_status: PRStatus
    
    # Agent outputs
    validated_alert: Optional[ValidatedAlert] = None
    thought_signature: Optional[ThoughtSignature] = None
    jira_ticket: Optional[JiraTicketResult] = None
    remediation_result: Optional[RemediationResult] = None
    
    # Timeline for UI display
    timeline: List["TimelineEvent"]


# models/timeline.py
class TimelineEventType(str, Enum):
    INCIDENT_CREATED = "incident_created"
    ALERT_VALIDATED = "alert_validated"
    INVESTIGATION_STARTED = "investigation_started"
    EVIDENCE_COLLECTED = "evidence_collected"
    ROOT_CAUSE_IDENTIFIED = "root_cause_identified"
    TICKET_CREATED = "ticket_created"
    FIX_GENERATED = "fix_generated"
    PR_CREATED = "pr_created"
    PR_MERGED = "pr_merged"
    INCIDENT_RESOLVED = "incident_resolved"
    ESCALATED_TO_HUMAN = "escalated_to_human"

class TimelineEvent(BaseModel):
    """Single event in incident timeline"""
    event_type: TimelineEventType
    timestamp: datetime
    agent: Optional[str] = None
    details: Dict[str, Any] = {}
    duration_ms: Optional[int] = None
```

---

## 11. Project Structure

```
resilix/
├── agent.py                    # Root agent definition (required by ADK)
├── main.py                     # FastAPI application entry point
├── pyproject.toml              # Project dependencies
├── Dockerfile.backend          # Backend container definition
├── Dockerfile.frontend         # Frontend container definition
├── docker-compose.yml          # Local development stack
├── cloudbuild.backend.yaml     # Cloud Build config for backend
├── cloudbuild.frontend.yaml    # Cloud Build config for frontend
├── .env.example                # Environment variable template
├── README.md                   # Project documentation
│
├── src/resilix/                # Backend source code
│   ├── __init__.py
│   │
│   ├── agents/                 # Agent definitions (hybrid architecture)
│   │   ├── __init__.py
│   │   ├── sentinel.py         # Sentinel - DETERMINISTIC with LLM fallback
│   │   ├── sherlock.py         # Sherlock - LLM Agent (Flash, high think)
│   │   ├── administrator.py    # Administrator - DETERMINISTIC service
│   │   ├── mechanic.py         # Mechanic - LLM Agent (Flash, high think)
│   │   └── orchestrator.py     # Root orchestrator configuration
│   │
│   ├── services/               # Deterministic services
│   │   ├── __init__.py
│   │   ├── sentinel_service.py # Deterministic alert processing
│   │   ├── admin_service.py    # Template-based Jira ticket creation
│   │   ├── pr_merge_policy.py  # Deterministic PR merge rules
│   │   ├── logging_client.py   # Cloud Logging / ELK client
│   │   ├── metrics_client.py   # Prometheus client
│   │   └── github_service.py   # GitHub API client
│   │
│   ├── tools/                  # Agent tools (for LLM agents)
│   │   ├── __init__.py
│   │   ├── log_tools.py        # Log querying tools (Sherlock)
│   │   ├── config_tools.py     # Config change detection (Sherlock)
│   │   ├── github_tools.py     # GitHub file/PR tools (Mechanic)
│   │   └── validation_tools.py # Code validation tools (Mechanic)
│   │
│   ├── models/                 # Pydantic data models
│   │   ├── __init__.py
│   │   ├── alert.py            # ValidatedAlert, Severity
│   │   ├── thought_signature.py # ThoughtSignature, Evidence
│   │   ├── remediation.py      # RemediationResult, ApprovalStatus, PRStatus
│   │   ├── incident.py         # IncidentDetailResponse, IncidentSummary
│   │   └── timeline.py         # TimelineEvent
│   │
│   ├── api/                    # FastAPI routes
│   │   ├── __init__.py
│   │   ├── webhooks.py         # POST /webhook/prometheus
│   │   ├── incidents.py        # GET/POST /incidents endpoints
│   │   └── health.py           # GET /health
│   │
│   ├── config/                 # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py         # Single model config (gemini-3-flash)
│   │
│   └── main.py                 # FastAPI app creation
│
├── frontend/                   # Dashboard application (Vite + React)
│   ├── src/
│   │   ├── components/
│   │   │   ├── SystemHealthStrip.tsx   # Health metrics bar
│   │   │   ├── IncidentFeed.tsx        # Incident list
│   │   │   ├── IncidentDetail.tsx      # Selected incident view
│   │   │   ├── Timeline.tsx            # Event timeline
│   │   │   ├── EvidencePanel.tsx       # RCA summary display
│   │   │   └── RemediationPanel.tsx    # PR status & approval button
│   │   ├── hooks/
│   │   │   ├── useIncidents.ts         # React Query hooks
│   │   │   └── useApproveMerge.ts      # Mutation hook
│   │   ├── types/
│   │   │   └── incident.ts             # TypeScript interfaces
│   │   ├── App.tsx                     # Main app component
│   │   └── main.tsx                    # Entry point
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── nginx.conf                      # SPA routing for production
│   └── Dockerfile
│
├── simulator/                  # DNS failure/recovery simulation
│   ├── __init__.py
│   ├── failure_injector.py     # Emit failure logs/metrics
│   ├── recovery_simulator.py   # Emit recovery pattern
│   ├── prometheus/
│   │   ├── prometheus.yml      # Prometheus config
│   │   └── alert_rules.yml     # DNS flapping alert rules
│   ├── alertmanager/
│   │   └── alertmanager.yml    # Webhook to Resilix backend
│   ├── dns_config/             # Mock config repo for PR target
│   │   └── coredns-config.yaml # Broken config (to be fixed)
│   ├── Dockerfile
│   └── README.md               # Simulator usage instructions
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── test_agents/
│   │   ├── test_sentinel.py    # Deterministic service tests
│   │   ├── test_sherlock.py    # LLM agent tests (mocked)
│   │   ├── test_administrator.py # Template service tests
│   │   └── test_mechanic.py    # LLM agent tests (mocked)
│   ├── test_services/
│   │   ├── test_sentinel_service.py
│   │   ├── test_admin_service.py
│   │   └── test_pr_merge_policy.py
│   ├── test_api/
│   │   ├── test_webhooks.py
│   │   ├── test_incidents.py
│   │   └── test_approve_merge.py
│   ├── test_integration/
│   │   └── test_full_pipeline.py
│   └── conftest.py             # Shared fixtures
│
└── scripts/
    ├── run_demo.sh             # Start full demo stack
    ├── trigger_failure.sh      # Trigger DNS failure simulation
    └── record_video.sh         # Screen recording helper
```

### 11.1 Key Directories

| Directory | Purpose |
|-----------|---------|
| `src/resilix/agents/` | Hybrid agents (2 LLM + 2 deterministic) |
| `src/resilix/services/` | Deterministic business logic |
| `src/resilix/api/` | FastAPI endpoints including approve-merge |
| `frontend/` | Vite + React observability dashboard |
| `simulator/` | DNS failure/recovery simulation for demo |
| `tests/` | Comprehensive test coverage |

---

## 12. Deployment Architecture

### 12.1 Service Topology

Resilix deploys as two separate Cloud Run services with supporting GCP infrastructure:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GOOGLE CLOUD PLATFORM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        CLOUD RUN SERVICES                            │   │
│  │  ┌─────────────────────────┐    ┌─────────────────────────┐         │   │
│  │  │    resilix-backend      │    │    resilix-frontend     │         │   │
│  │  │    (FastAPI + ADK)      │    │    (Vite + React)       │         │   │
│  │  │                         │    │                         │         │   │
│  │  │  • /webhook/prometheus  │◄───│  • Polls /incidents     │         │   │
│  │  │  • /incidents           │    │  • Posts /approve-merge │         │   │
│  │  │  • /incidents/{id}      │    │                         │         │   │
│  │  │  • /incidents/{id}/     │    │                         │         │   │
│  │  │    approve-merge        │    │                         │         │   │
│  │  └───────────┬─────────────┘    └─────────────────────────┘         │   │
│  └──────────────│───────────────────────────────────────────────────────┘   │
│                 │                                                            │
│  ┌──────────────▼───────────────────────────────────────────────────────┐   │
│  │                           STORAGE LAYER                               │   │
│  │  ┌─────────────────────────┐    ┌─────────────────────────┐         │   │
│  │  │    Secret Manager       │    │    In-Memory Store      │         │   │
│  │  │                         │    │    (MVP) or Cloud SQL   │         │   │
│  │  │  • GEMINI_API_KEY      │    │                         │         │   │
│  │  │  • GITHUB_TOKEN        │    │  • Session state        │         │   │
│  │  │  • JIRA_API_TOKEN      │    │  • Incident data        │         │   │
│  │  └─────────────────────────┘    └─────────────────────────┘         │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                          CLOUD BUILD (CI/CD)                          │   │
│  │  • Triggered on push to main                                          │   │
│  │  • Builds and deploys each service independently                      │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                 │                          │                     │
                 ▼                          ▼                     ▼
         ┌───────────────┐         ┌───────────────┐     ┌───────────────┐
         │   Prometheus  │         │    GitHub     │     │     Jira      │
         │  Alertmanager │         │      API      │     │    Cloud      │
         └───────────────┘         └───────────────┘     └───────────────┘
```

### 12.2 Backend Container Configuration

```dockerfile
# Dockerfile.backend
FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system -e .

# Copy application code
COPY src/ ./src/

# Expose port (Cloud Run uses 8080 by default)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["uvicorn", "src.resilix.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 12.3 Frontend Container Configuration

```dockerfile
# Dockerfile.frontend
FROM node:20-alpine as builder

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY frontend/ ./

# Build the app
RUN npm run build

# Production image
FROM nginx:alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config for SPA routing
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
```

### 12.4 Cloud Build Configuration

```yaml
# cloudbuild.backend.yaml
steps:
  # Build the container
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/resilix-backend:$COMMIT_SHA'
      - '-t'
      - 'gcr.io/$PROJECT_ID/resilix-backend:latest'
      - '-f'
      - 'Dockerfile.backend'
      - '.'

  # Push to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/resilix-backend:$COMMIT_SHA'

  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/resilix-backend:latest'

  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'gcloud'
      - 'run'
      - 'deploy'
      - 'resilix-backend'
      - '--image'
      - 'gcr.io/$PROJECT_ID/resilix-backend:$COMMIT_SHA'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--set-secrets'
      - 'GEMINI_API_KEY=gemini-api-key:latest,GITHUB_TOKEN=github-token:latest,JIRA_API_TOKEN=jira-api-token:latest'

timeout: '1200s'
```

```yaml
# cloudbuild.frontend.yaml
steps:
  # Build the container
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'build'
      - '-t'
      - 'gcr.io/$PROJECT_ID/resilix-frontend:$COMMIT_SHA'
      - '-t'
      - 'gcr.io/$PROJECT_ID/resilix-frontend:latest'
      - '-f'
      - 'Dockerfile.frontend'
      - '.'

  # Push to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/resilix-frontend:$COMMIT_SHA'

  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - 'gcr.io/$PROJECT_ID/resilix-frontend:latest'

  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'gcloud'
      - 'run'
      - 'deploy'
      - 'resilix-frontend'
      - '--image'
      - 'gcr.io/$PROJECT_ID/resilix-frontend:$COMMIT_SHA'
      - '--region'
      - 'us-central1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--set-env-vars'
      - 'VITE_API_URL=https://resilix-backend-xxxxx-uc.a.run.app'

timeout: '600s'
```

### 12.5 Environment Configuration

**Secret Manager Setup:**

```bash
# Create secrets in Secret Manager
gcloud secrets create gemini-api-key --data-file=- <<< "$GEMINI_API_KEY"
gcloud secrets create github-token --data-file=- <<< "$GITHUB_TOKEN"
gcloud secrets create jira-api-token --data-file=- <<< "$JIRA_API_TOKEN"

# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

**Environment Variables:**

```bash
# Backend (.env.example)
GEMINI_API_KEY=<from-secret-manager>
GITHUB_TOKEN=<from-secret-manager>
JIRA_API_TOKEN=<from-secret-manager>
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=resilix@company.com
LOG_LEVEL=INFO

# Frontend (build-time)
VITE_API_URL=https://resilix-backend-xxxxx-uc.a.run.app
```

### 12.6 CORS Configuration

```python
# Backend CORS setup
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://resilix-frontend-xxxxx-uc.a.run.app",  # Production frontend
        "http://localhost:5173",  # Local development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### 12.7 MVP Simplification

For the hackathon, use these simplified approaches:

| Component | MVP Approach | Production Approach |
|-----------|--------------|---------------------|
| **Session Store** | In-memory dict | Cloud SQL PostgreSQL |
| **Incident Persistence** | In-memory | Cloud SQL + Cloud Storage |
| **Secrets** | Environment variables | Secret Manager |
| **Logging** | stdout/stderr | Cloud Logging |
| **Monitoring** | None | Cloud Monitoring |

```python
# MVP: In-memory session store
from google.adk.sessions import InMemorySessionService

session_service = InMemorySessionService()

# Production: Database-backed sessions
# from google.adk.sessions import DatabaseSessionService
# session_service = DatabaseSessionService(connection_string=os.getenv("DATABASE_URL"))
```

### 12.8 Local Development (Docker Compose)

```yaml
# docker-compose.yml - For local development only
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8080:8080"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - JIRA_URL=${JIRA_URL}
      - JIRA_USERNAME=${JIRA_USERNAME}
      - JIRA_API_TOKEN=${JIRA_API_TOKEN}
      - GITHUB_TOKEN=${GITHUB_TOKEN}
    volumes:
      - ./src:/app/src:ro

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "3000:8080"
    environment:
      - VITE_API_URL=http://localhost:8080

  # DNS Failure Simulator
  simulator:
    build:
      context: ./simulator
    depends_on:
      - prometheus
    environment:
      - PROMETHEUS_PUSHGATEWAY=http://prometheus:9091

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./simulator/prometheus.yml:/etc/prometheus/prometheus.yml

  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - ./simulator/alertmanager.yml:/etc/alertmanager/alertmanager.yml
```

---

## 13. Testing Strategy

### 13.1 Unit Tests

```python
# tests/test_agents/test_sentinel.py
import pytest
from unittest.mock import AsyncMock, patch
from agents.sentinel import sentinel_agent
from models.alert import ValidatedAlert, Severity

@pytest.fixture
def sample_prometheus_alert():
    return {
        "status": "firing",
        "labels": {
            "alertname": "HighErrorRate",
            "service": "checkout-service",
            "severity": "critical"
        },
        "annotations": {
            "summary": "High error rate detected",
            "description": "Error rate is 5.2%"
        },
        "startsAt": "2026-02-02T10:30:00Z"
    }

@pytest.mark.asyncio
async def test_sentinel_validates_actionable_alert(sample_prometheus_alert):
    """Sentinel should mark high-severity alerts as actionable"""
    
    with patch('agents.sentinel.check_maintenance_window') as mock_maintenance:
        mock_maintenance.return_value = {"in_maintenance": False}
        
        result = await sentinel_agent.process(sample_prometheus_alert)
        
        assert isinstance(result, ValidatedAlert)
        assert result.is_actionable is True
        assert result.severity == Severity.CRITICAL

@pytest.mark.asyncio
async def test_sentinel_filters_maintenance_window(sample_prometheus_alert):
    """Sentinel should not escalate alerts during maintenance"""
    
    with patch('agents.sentinel.check_maintenance_window') as mock_maintenance:
        mock_maintenance.return_value = {
            "in_maintenance": True,
            "window": {"reason": "Scheduled deployment"}
        }
        
        result = await sentinel_agent.process(sample_prometheus_alert)
        
        assert result.is_actionable is False
        assert "maintenance" in result.triage_reason.lower()
```

### 13.2 Integration Tests

```python
# tests/test_integration/test_full_pipeline.py
import pytest
from httpx import AsyncClient
from main import app

@pytest.fixture
async def test_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_webhook_accepts_prometheus_alert(test_client):
    """Webhook endpoint should accept valid Prometheus alerts"""
    
    webhook_payload = {
        "version": "4",
        "groupKey": "test-group",
        "status": "firing",
        "receiver": "resilix",
        "alerts": [{
            "status": "firing",
            "labels": {"alertname": "TestAlert", "service": "test-service"},
            "annotations": {"summary": "Test alert"},
            "startsAt": "2026-02-02T10:30:00Z"
        }]
    }
    
    response = await test_client.post("/webhook/prometheus", json=webhook_payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert "incident_id" in data
```

### 13.3 Mock Services

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def mock_jira_client():
    """Mock Atlassian MCP for testing"""
    client = AsyncMock()
    client.create_issue.return_value = {
        "key": "SRE-1234",
        "self": "https://company.atlassian.net/rest/api/2/issue/12345"
    }
    return client

@pytest.fixture
def mock_github_client():
    """Mock GitHub MCP for testing"""
    client = AsyncMock()
    client.create_pull_request.return_value = {
        "number": 456,
        "html_url": "https://github.com/acme/service/pull/456"
    }
    client.merge_pull_request.return_value = {"merged": True}
    return client
```

---

## 14. Demo Strategy

### 14.1 Demo Narrative

> **Scenario**: Simulate a controllable DNS misconfiguration that causes service flapping and downstream errors, then auto-remediate through configuration fix.

This demo showcases Resilix's ability to:
1. Detect complex infrastructure issues from correlated log patterns
2. Perform root cause analysis to identify configuration errors
3. Generate and deploy configuration fixes via GitHub PR
4. Show measurable recovery with MTTR metrics

### 14.2 Demo Timeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DNS FAILURE SIMULATION DEMO                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  FAILURE PHASE (0:00 - 0:30)                                                │
│  ├─ failure-injector starts emitting:                                       │
│  │   • TargetHealthFlapping events (10/sec)                                 │
│  │   • queue_depth metrics rising (1000 → 5000)                             │
│  │   • unhealthy_target_ratio increasing (0.0 → 0.6)                        │
│  │                                                                          │
│  ├─ Prometheus alert fires when thresholds exceeded:                        │
│  │   • flapping_events/min > 50                                             │
│  │   • queue_depth sustained > 1000 for 30s                                 │
│  │   • unhealthy_targets > 0.3                                              │
│  │                                                                          │
│  INVESTIGATION (0:30 - 0:45)                                                │
│  ├─ Sentinel validates alert (deterministic)                                │
│  ├─ Sherlock investigates with high thinking:                               │
│  │   • Queries logs: TargetHealthFlapping correlation                       │
│  │   • Checks recent config changes                                         │
│  │   • Identifies pattern: DNS resolver failure                             │
│  ├─ Sherlock concludes:                                                     │
│  │   • root_cause_category: config_error                                    │
│  │   • target_artifact: infra/dns/coredns-config.yaml                      │
│  │   • confidence: 0.94                                                     │
│  │                                                                          │
│  REMEDIATION (0:45 - 1:00)                                                  │
│  ├─ Administrator creates Jira ticket (deterministic)                       │
│  ├─ Mechanic generates fix PR:                                              │
│  │   • Restore valid resolver/forward rule                                  │
│  │   • Re-enable failover: DISABLED_MANUAL → AUTO                          │
│  ├─ CI runs on PR                                                           │
│  ├─ Dashboard shows: "Awaiting Approval"                                    │
│  │                                                                          │
│  APPROVAL & RECOVERY (1:00 - 1:30)                                          │
│  ├─ Human clicks "Approve Merge" in dashboard                               │
│  ├─ PR merges automatically                                                 │
│  ├─ recovery-simulator starts emitting:                                     │
│  │   • queue_depth trending down (5000 → 100)                               │
│  │   • unhealthy_targets dropping (0.6 → 0.0)                               │
│  │   • "propagation_stabilized" log event                                   │
│  ├─ Prometheus alert auto-resolves                                          │
│  │                                                                          │
│  DASHBOARD SHOWS                                                            │
│  ├─ Complete timeline: Alert → RCA → Jira → PR → Merge → Resolved          │
│  ├─ Measured MTTR: ~90 seconds                                              │
│  ├─ Thought signature summary visible                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 14.3 Simulator Components

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| **failure-injector** | Emit failure logs and metrics | Python script pushing to Prometheus |
| **recovery-simulator** | Emit recovery pattern | Triggered after PR approval |
| **dns-config-repo** | Target for fix PR | Mock GitHub repo with YAML config |

### 14.4 Failure Injector

```python
# simulator/failure_injector.py
"""Injects DNS failure patterns into Prometheus and logs"""

import asyncio
import random
from datetime import datetime
from prometheus_client import CollectorRegistry, Gauge, Counter, push_to_gateway

class FailureInjector:
    """Simulates DNS resolver failure symptoms"""
    
    def __init__(self, pushgateway_url: str, log_endpoint: str):
        self.pushgateway = pushgateway_url
        self.log_endpoint = log_endpoint
        
        # Prometheus metrics
        self.registry = CollectorRegistry()
        self.queue_depth = Gauge(
            'dns_queue_depth', 
            'DNS query queue depth',
            registry=self.registry
        )
        self.unhealthy_ratio = Gauge(
            'dns_unhealthy_target_ratio',
            'Ratio of unhealthy DNS targets',
            registry=self.registry
        )
        self.flapping_events = Counter(
            'dns_target_health_flapping_total',
            'Total target health flapping events',
            registry=self.registry
        )
    
    async def start_failure_phase(self, duration_seconds: int = 30):
        """Emit failure pattern for specified duration"""
        
        start_time = datetime.utcnow()
        print(f"[INJECTOR] Starting failure phase at {start_time}")
        
        for i in range(duration_seconds * 2):  # 2 updates per second
            # Escalating queue depth
            current_depth = 1000 + (i * 100) + random.randint(0, 200)
            self.queue_depth.set(min(current_depth, 5000))
            
            # Increasing unhealthy ratio
            ratio = min(0.6, 0.1 + (i * 0.02))
            self.unhealthy_ratio.set(ratio)
            
            # Flapping events
            self.flapping_events.inc(random.randint(5, 15))
            
            # Push to Prometheus
            push_to_gateway(
                self.pushgateway, 
                job='dns-resolver',
                registry=self.registry
            )
            
            # Emit logs
            await self._emit_failure_logs()
            
            await asyncio.sleep(0.5)
        
        print(f"[INJECTOR] Failure phase complete")
    
    async def _emit_failure_logs(self):
        """Emit structured failure logs"""
        logs = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "ERROR",
                "service": "dns-resolver",
                "event": "TargetHealthFlapping",
                "target": f"dns-resolver-{random.randint(1, 3)}",
                "details": "Health check alternating between healthy/unhealthy"
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "WARN", 
                "service": "dns-resolver",
                "event": "queue_depth_exceeded",
                "value": self.queue_depth._value.get(),
                "threshold": 1000
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "ERROR",
                "service": "dns-resolver", 
                "event": "upstream_connection_failed",
                "reason": "NXDOMAIN",
                "upstream": "10.0.0.1:53"
            }
        ]
        
        # In real implementation, send to log aggregator
        for log in logs:
            print(f"[LOG] {log}")
```

### 14.5 Recovery Simulator

```python
# simulator/recovery_simulator.py
"""Simulates recovery after PR merge"""

import asyncio
from datetime import datetime
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

class RecoverySimulator:
    """Simulates DNS resolver recovery after config fix"""
    
    def __init__(self, pushgateway_url: str):
        self.pushgateway = pushgateway_url
        self.registry = CollectorRegistry()
        
        self.queue_depth = Gauge(
            'dns_queue_depth',
            'DNS query queue depth', 
            registry=self.registry
        )
        self.unhealthy_ratio = Gauge(
            'dns_unhealthy_target_ratio',
            'Ratio of unhealthy DNS targets',
            registry=self.registry
        )
    
    async def start_recovery_phase(self, duration_seconds: int = 30):
        """Emit recovery pattern showing gradual improvement"""
        
        start_time = datetime.utcnow()
        print(f"[RECOVERY] Starting recovery phase at {start_time}")
        
        # Start from failure state
        current_depth = 5000
        current_ratio = 0.6
        
        for i in range(duration_seconds * 2):
            # Decreasing queue depth
            current_depth = max(100, current_depth - random.randint(100, 200))
            self.queue_depth.set(current_depth)
            
            # Decreasing unhealthy ratio
            current_ratio = max(0.0, current_ratio - 0.02)
            self.unhealthy_ratio.set(current_ratio)
            
            # Push to Prometheus
            push_to_gateway(
                self.pushgateway,
                job='dns-resolver',
                registry=self.registry
            )
            
            # Emit recovery logs
            await self._emit_recovery_logs(current_depth, current_ratio)
            
            await asyncio.sleep(0.5)
        
        # Final stabilization log
        print(f"[LOG] {{'event': 'propagation_stabilized', 'latency_ms': 23}}")
        print(f"[RECOVERY] Recovery phase complete. Service healthy.")
    
    async def _emit_recovery_logs(self, depth: int, ratio: float):
        """Emit recovery progress logs"""
        logs = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "service": "dns-resolver",
                "event": "config_reload_triggered",
                "source": "resilix-pr-merge"
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "service": "dns-resolver",
                "event": "queue_depth_decreasing",
                "value": depth,
                "trend": "down"
            }
        ]
        
        if ratio < 0.1:
            logs.append({
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "service": "dns-resolver",
                "event": "target_health_restored",
                "target": "all"
            })
        
        for log in logs:
            print(f"[LOG] {log}")
```

### 14.6 Prometheus Alert Configuration

```yaml
# simulator/prometheus/alert_rules.yml
groups:
  - name: resilix_dns_demo
    rules:
      - alert: DNSResolverFlapping
        expr: rate(dns_target_health_flapping_total[1m]) > 50
        for: 30s
        labels:
          severity: critical
          service: dns-resolver
          category: config_error
        annotations:
          summary: "DNS resolver targets are flapping"
          description: "Target health flapping rate is {{ $value }}/min"
          
      - alert: DNSQueueDepthHigh
        expr: dns_queue_depth > 1000
        for: 30s
        labels:
          severity: high
          service: dns-resolver
        annotations:
          summary: "DNS query queue depth is high"
          description: "Queue depth is {{ $value }}"
          
      - alert: DNSUnhealthyTargets
        expr: dns_unhealthy_target_ratio > 0.3
        for: 30s
        labels:
          severity: critical
          service: dns-resolver
        annotations:
          summary: "High ratio of unhealthy DNS targets"
          description: "{{ $value | humanizePercentage }} of targets are unhealthy"
```

### 14.7 Fix Template

The Mechanic agent will generate a PR with this type of fix:

```yaml
# BEFORE (broken) - infra/dns/coredns-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns-config
data:
  Corefile: |
    .:53 {
        errors
        health
        kubernetes cluster.local in-addr.arpa ip6.arpa {
           pods insecure
           fallthrough in-addr.arpa ip6.arpa
        }
        forward . 10.0.0.1:53  # Single resolver - no failover!
        cache 30
        loop
        reload
        loadbalance
    }
  failover_mode: "DISABLED_MANUAL"  # Failover disabled!
```

```yaml
# AFTER (fixed by Mechanic) - infra/dns/coredns-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns-config
  # Fixed by Resilix - Incident INC-A1B2C3D4
data:
  Corefile: |
    .:53 {
        errors
        health
        kubernetes cluster.local in-addr.arpa ip6.arpa {
           pods insecure
           fallthrough in-addr.arpa ip6.arpa
        }
        forward . 10.0.0.1:53 10.0.0.2:53 {  # Restored backup resolver
           policy round_robin
           health_check 5s
        }
        cache 30
        loop
        reload
        loadbalance
    }
  failover_mode: "AUTO"  # Re-enabled automatic failover
```

### 14.8 Demo Video Script (3 Minutes)

```
[0:00-0:30] INTRODUCTION
- "Hi, I'm presenting Resilix - the world's first Autonomous SRE"
- Problem statement: 3 AM PagerDuty nightmare, $16,700/min downtime
- "Watch what happens when DNS goes wrong - and fixes itself"

[0:30-1:15] LIVE DEMO - FAILURE
- Show dashboard: System healthy (green indicators)
- "Let's simulate a DNS misconfiguration..."
- Trigger failure-injector
- Watch metrics rise: queue_depth, flapping events
- Alert fires: "DNS Resolver Flapping - CRITICAL"
- Resilix starts processing (show incident appearing in feed)

[1:15-1:45] LIVE DEMO - INVESTIGATION  
- Sherlock investigating (timeline updating in real-time)
- "Root cause: config_error in coredns-config.yaml"
- Evidence panel shows correlated logs
- Jira ticket auto-created
- PR created with config fix
- CI running... CI passed!
- "Awaiting Approval" status

[1:45-2:15] LIVE DEMO - RECOVERY
- Click "Approve Merge" button
- PR merges
- Recovery metrics start trending down
- Alert auto-resolves
- Incident marked RESOLVED
- MTTR displayed: "47 seconds"

[2:15-2:45] TECHNICAL HIGHLIGHTS
- "4 agents, only 2 use LLM - efficiency by design"
- Gemini 3 Flash with high thinking for deep reasoning
- Thought signatures preserve context across agents
- Full audit trail: Jira + GitHub PR

[2:45-3:00] CONCLUSION
- "From alert to fix in under a minute"
- "No 3 AM wake-up. Full audit trail. Infrastructure saved."
- "Resilix - Autonomous SRE powered by Gemini 3"
```

---

## 15. Implementation Phases

> **Execution Order**: Backend contract first, frontend second, simulator third, agent refinement fourth.

### Phase 1: Backend Contract (Priority)

**Goal**: Finalize and implement all API endpoints

**Tasks**:
- [ ] Implement `/webhook/prometheus` endpoint (accept AlertManager webhooks)
- [ ] Implement `/incidents` endpoint (list all incidents with summary)
- [ ] Implement `/incidents/{id}` endpoint (full incident detail)
- [ ] Implement `/incidents/{id}/approve-merge` endpoint (approval gate)
- [ ] Implement `/health` endpoint (health check)
- [ ] Define response schemas with all frontend-required fields
- [ ] Implement mock responses for frontend development
- [ ] Add CORS configuration for frontend domain
- [ ] Set up in-memory session store for MVP

**Response Schema Requirements**:
```python
# All incidents must include:
- incident_id, status, severity, service_name
- created_at, resolved_at, mttr_seconds
- approval_status (pending/approved/not_required)
- pr_status (not_created/pending_ci/ci_passed/merged)
- timeline (array of structured events)
- thought_signature (RCA summary for display)
```

**Deliverable**: Backend API fully functional with mock data, ready for frontend integration

### Phase 2: Frontend Development

**Goal**: Build observability dashboard against mock/real backend

**Tasks**:
- [ ] Initialize Vite + React project in `frontend/`
- [ ] Set up React Query for API polling
- [ ] Implement System Health Strip component
- [ ] Implement Incident Feed component with polling
- [ ] Implement Incident Detail view with timeline
- [ ] Implement Evidence Panel (thought signature summary)
- [ ] Implement Remediation Panel with PR status
- [ ] Implement "Approve Merge" button with POST action
- [ ] Add loading states and error handling
- [ ] Style with Tailwind CSS
- [ ] Test against mock backend responses
- [ ] Connect to real backend
- [ ] Create Dockerfile.frontend
- [ ] Deploy to Cloud Run (separate service)

**Deliverable**: Fully functional dashboard showing incidents, timeline, and approval gate

### Phase 3: DNS Simulator

**Goal**: Create controllable failure/recovery simulation

**Tasks**:
- [ ] Create `simulator/` directory
- [ ] Implement `failure_injector.py` (emit failure logs/metrics)
- [ ] Implement `recovery_simulator.py` (emit recovery pattern)
- [ ] Set up Prometheus alert rules for DNS flapping
- [ ] Configure AlertManager to webhook to Resilix
- [ ] Create mock DNS config repo for PR target
- [ ] Create `coredns-config.yaml` template (broken state)
- [ ] Create fix template for Mechanic reference
- [ ] Test end-to-end: failure → alert → recovery
- [ ] Add simulator to docker-compose

**Deliverable**: Controllable demo that triggers realistic incident flow

### Phase 4: Agent Refinement

**Goal**: Optimize agents for DNS scenario and hybrid architecture

**Tasks**:
- [ ] Refactor Sentinel to deterministic service with LLM fallback
- [ ] Convert Administrator to deterministic template-based service
- [ ] Tune Sherlock prompts for DNS/config error detection
- [ ] Tune Mechanic prompts for YAML config fixes
- [ ] Implement PR merge policy (deterministic)
- [ ] Test full pipeline with DNS scenario
- [ ] Add timeline events for each agent step
- [ ] Verify thought signature includes all evidence
- [ ] Test approval flow end-to-end

**Deliverable**: Agents optimized for demo scenario with reliable output

### Phase 5: Integration & Polish

**Goal**: Production-like, repeatable demo simulation with API-first integrations and clean handoff into dedicated demo repositories.

**Status Note (Current Architecture)**:
- Runtime integrations are API-first (Jira/GitHub direct APIs), not MCP runtime servers.
- `USE_MOCK_PROVIDERS` is canonical; `USE_MOCK_MCP` is legacy compatibility only.
- Backend and frontend are independently deployable Cloud Run services.

**Phase 5 Objective**:
- Make the demo deterministic, replayable, and judge-friendly by shipping a simulator toolchain and demo repos that can consistently produce:
  - realistic incident trigger patterns,
  - observable lifecycle transitions in UI,
  - real Jira board movement and GitHub PR lifecycle.

#### 5.1 Deliverables (Must Ship)
- [ ] `resilix-demo-app` repository (primary PR target for code/config remediation).
- [ ] `resilix-demo-config` repository (secondary PR target for infra/config scenario).
- [ ] `simulator/` package in current repo with replayable alert/log generators.
- [ ] End-to-end runbook: local and deployed smoke scripts.
- [ ] Cloud Build/Run env + secrets documented and validated for backend + frontend.
- [ ] 3-minute recording script and final capture checklist.

#### 5.2 Repository/Package Strategy (Implement Here First, Then Split)
**Recommended execution order**:
1. Build and validate all simulator code inside this existing repo first.
2. Stabilize contracts and replay scripts against deployed backend/frontend.
3. Extract to dedicated demo repositories once behavior is stable.

**Repository map**:
1. `resilix` (current)
- Backend service, frontend dashboard, shared models/contracts, simulator package (initially).
2. `resilix-demo-app`
- Minimal service/app artifacts that Resilix modifies through PRs.
- Include intentional reversible misconfig states and golden fixed states.
3. `resilix-demo-config`
- Infra-oriented config targets for non-code remediation path.
4. (Optional) `resilix-demo-runbooks`
- Presentation scripts, sample payloads, one-command demo orchestration docs.

**Simulator package shape (inside current repo first)**:
- `simulator/fixtures/`:
  - canonical alert payloads (critical/high), flapping/backlog variants.
- `simulator/generators/`:
  - deterministic timeline/log emitters (seeded for repeatability).
- `simulator/scenarios/`:
  - scenario registry (baseline, flapping, dependency timeout).
- `simulator/scripts/`:
  - `trigger_alert.py`, `run_scenario.py`, `verify_lifecycle.py`.

#### 5.3 API and UX Validation Contract (Phase 5 Gates)
- [ ] `POST /webhook/prometheus` accepts seeded simulated alerts and returns `incident_id`.
- [ ] `GET /incidents` and `GET /incidents/{id}` reflect lifecycle progression.
- [ ] `POST /incidents/{id}/approve-merge` transitions incident to resolved path.
- [ ] Jira issue transitions visible on board:
  - To Do -> In Progress -> In Review -> Done.
- [ ] GitHub PR lifecycle visible:
  - branch -> commit -> PR -> CI pass -> approval -> squash merge.
- [ ] Frontend reflects timeline + evidence + remediation + approval gate state.

#### 5.4 Required Secrets/Env for Deployed E2E Demo
- [ ] `GEMINI_API_KEY`
- [ ] `DATABASE_URL`
- [ ] `USE_MOCK_PROVIDERS=false`
- [ ] `GITHUB_TOKEN`
- [ ] `GITHUB_OWNER`
- [ ] `GITHUB_DEFAULT_BASE_BRANCH`
- [ ] `JIRA_URL`
- [ ] `JIRA_USERNAME`
- [ ] `JIRA_API_TOKEN`
- [ ] `JIRA_PROJECT_KEY`
- [ ] `JIRA_ISSUE_TYPE`
- [ ] Jira transition config:
  - `JIRA_STATUS_TODO`
  - `JIRA_STATUS_IN_PROGRESS`
  - `JIRA_STATUS_IN_REVIEW`
  - `JIRA_STATUS_DONE`

#### 5.5 Phase 5 Implementation Tasks (Decision Complete)
1. Simulator baseline
- [ ] Add deterministic scenario fixtures and payload generators.
- [ ] Add one-command trigger script to create incident and print `incident_id`.
- [ ] Add poll script to track lifecycle until resolved/failed with timeout.

2. End-to-end assertions
- [ ] Validate incident status path (`processing` -> `awaiting_approval` -> `resolved`).
- [ ] Validate Jira transition trace entries.
- [ ] Validate PR metadata and merge policy outcomes.
- [ ] Validate MTTR sanity (`resolved_at >= created_at`) and reject negative values in checks.

3. Demo repo extraction
- [ ] Create `resilix-demo-app` and `resilix-demo-config`.
- [ ] Move stable fixture targets from current repo into demo repos.
- [ ] Update backend config to target new repos by default in demo mode.
- [ ] Re-run full smoke against deployed services and new repos.

4. Cloud deployment hardening
- [ ] Verify backend Cloud Run env/secret bindings.
- [ ] Deploy frontend Cloud Run service and set backend base URL.
- [ ] Validate CORS across deployed frontend/backend.
- [ ] Add `/health` pre-demo check script.

5. Presentation assets
- [ ] Record deterministic demo run with timestamped checkpoints.
- [ ] Finalize submission description (Gemini feature mapping + impact).
- [ ] Publish concise operator runbook for judges/reviewers.

#### 5.6 Phase 5 Test Plan
- [ ] Unit: simulator scenario parser/generator determinism (seeded outputs).
- [ ] Integration: trigger -> incident creation -> PR creation -> approval -> merge.
- [ ] Contract: API response schema snapshots for frontend compatibility.
- [ ] Smoke (deployed): run scripted alert and verify Jira + GitHub side effects.
- [ ] Regression: existing backend/frontend suites remain green.

#### 5.7 Acceptance Criteria (Phase 5 Complete)
1. One command (or single script sequence) can trigger and complete a full incident lifecycle against deployed services.
2. Jira and GitHub show real, non-mock progression for the same incident.
3. Frontend displays live incident progression and final resolved state.
4. Demo scenario is repeatable with predictable timings and outputs.
5. Repositories are split (`resilix-demo-app`, `resilix-demo-config`) and wired in deployed config.

**Deliverable**: Demo-simulation stack is production-like, repeatable, and submission-ready.

### Development Timeline Summary

| Phase | Focus | Key Deliverable |
|-------|-------|-----------------|
| **1** | Backend Contract | API endpoints with mock data |
| **2** | Frontend | Dashboard with approval gate |
| **3** | DNS Simulator | Controllable failure/recovery |
| **4** | Agent Refinement | Optimized for DNS scenario |
| **5** | Integration & Demo Simulation | Repeatable deployed E2E demo with real Jira/GitHub side effects |

---

## 16. Frontend Architecture

### 16.1 Dashboard Design Philosophy

Resilix provides an **observability + action audit interface**, NOT a chatbot. The frontend is:

- **Read-only** except for one control: the "Approve Merge" action
- **Real-time**: Polls backend for incident updates
- **Information-dense**: Shows incident status, timeline, evidence, and remediation at a glance
- **SRE-focused**: Designed for incident responders, not end users

### 16.2 MVP UI Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SYSTEM HEALTH STRIP                                                         │
│  [Alert Rate: 2/hr] [Open Incidents: 1] [Auto-Resolve: 94%] [MTTR: 47s]     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INCIDENT FEED                        │  LIVE INCIDENT DETAIL               │
│  ┌──────────────────────────────────┐ │  ┌────────────────────────────────┐ │
│  │ ● INC-A1B2C3D4 [CRITICAL]       │ │  │ Timeline                       │ │
│  │   dns-resolver | 2m ago         │ │  │ ● Alert Received       00:00   │ │
│  │   Status: Awaiting Approval     │ │  │ ● RCA Complete         00:12   │ │
│  ├──────────────────────────────────┤ │  │ ● Jira Created         00:14   │ │
│  │ ○ INC-E5F6G7H8 [HIGH]           │ │  │ ● PR Created           00:23   │ │
│  │   checkout-svc | 15m ago        │ │  │ ○ Awaiting Approval    00:23   │ │
│  │   Status: Resolved (47s MTTR)   │ │  └────────────────────────────────┘ │
│  ├──────────────────────────────────┤ │                                     │
│  │ ○ INC-I9J0K1L2 [MEDIUM]         │ │  EVIDENCE PANEL                     │
│  │   payment-svc | 1h ago          │ │  ┌────────────────────────────────┐ │
│  │   Status: Resolved (23s MTTR)   │ │  │ Root Cause: config_error       │ │
│  └──────────────────────────────────┘ │  │ Confidence: 94%                │ │
│                                        │  │                                │ │
│                                        │  │ Top Correlated Evidence:       │ │
│                                        │  │ • TargetHealthFlapping x42     │ │
│                                        │  │ • queue_depth > 1000 (5 min)   │ │
│                                        │  │ • NXDOMAIN errors increasing   │ │
│                                        │  └────────────────────────────────┘ │
│                                        │                                     │
│                                        │  REMEDIATION PANEL                  │
│                                        │  ┌────────────────────────────────┐ │
│                                        │  │ Action: config_fix             │ │
│                                        │  │ Target: coredns-config.yaml    │ │
│                                        │  │                                │ │
│                                        │  │ PR: #456 (CI Passed ✓)         │ │
│                                        │  │ Jira: SRE-789                  │ │
│                                        │  │                                │ │
│                                        │  │ ┌────────────────────────────┐ │ │
│                                        │  │ │     [APPROVE MERGE]        │ │ │
│                                        │  │ └────────────────────────────┘ │ │
│                                        │  └────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 16.3 Component Breakdown

| Component | Purpose | Data Source |
|-----------|---------|-------------|
| **System Health Strip** | High-level metrics overview | `/incidents` aggregation |
| **Incident Feed** | List of active/recent incidents | `GET /incidents` |
| **Timeline** | Step-by-step incident progression | `incident.timeline` array |
| **Evidence Panel** | Thought signature summary | `incident.thought_signature` |
| **Remediation Panel** | Action status and approval | `incident.remediation_status` |
| **Approve Merge Button** | Human approval gate | `POST /incidents/{id}/approve-merge` |

### 16.4 Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Framework** | Vite + React | Fast build, simple setup for hackathon |
| **State Management** | React Query | Automatic polling, cache management |
| **Styling** | Tailwind CSS | Rapid UI development |
| **HTTP Client** | Axios | Clean API calls |
| **Deployment** | Cloud Run | Same platform as backend |

### 16.5 API Integration

```typescript
// hooks/useIncidents.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Fetch all incidents (polling every 5 seconds)
export function useIncidents() {
  return useQuery({
    queryKey: ['incidents'],
    queryFn: async () => {
      const { data } = await axios.get(`${API_BASE}/incidents`);
      return data;
    },
    refetchInterval: 5000, // Poll every 5 seconds
  });
}

// Fetch single incident detail
export function useIncidentDetail(incidentId: string | null) {
  return useQuery({
    queryKey: ['incident', incidentId],
    queryFn: async () => {
      const { data } = await axios.get(`${API_BASE}/incidents/${incidentId}`);
      return data;
    },
    enabled: !!incidentId,
    refetchInterval: 2000, // Poll more frequently for active incident
  });
}

// Approve merge action
export function useApproveMerge() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (incidentId: string) => {
      const { data } = await axios.post(
        `${API_BASE}/incidents/${incidentId}/approve-merge`
      );
      return data;
    },
    onSuccess: () => {
      // Invalidate and refetch incidents
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
    },
  });
}
```

### 16.6 Key UI States

| Incident State | UI Indication | User Action |
|----------------|---------------|-------------|
| **alert_received** | Yellow indicator, "Investigating..." | None (watch) |
| **rca_complete** | Blue indicator, evidence visible | None (watch) |
| **remediation_in_progress** | Orange indicator, PR link | None (watch) |
| **awaiting_approval** | Red pulsing indicator, button enabled | Click "Approve Merge" |
| **merged** | Green indicator, "Merging..." | None (watch) |
| **resolved** | Green checkmark, MTTR displayed | None (complete) |

### 16.7 Responsive Design

The dashboard is optimized for desktop (1280px+) but supports tablet viewing:

```css
/* Breakpoints */
@media (min-width: 1024px) {
  /* Two-column layout: Feed | Detail */
}
@media (max-width: 1023px) {
  /* Stacked layout: Feed above Detail */
}
```

---

## Appendix A: Dependencies

```toml
# pyproject.toml
[project]
name = "resilix"
version = "1.0.0"
description = "Autonomous Site Reliability Engineer"
requires-python = ">=3.12"
dependencies = [
    "google-adk>=0.1.0",
    "google-genai>=0.5.0",
    "mcp>=1.0.0",
    "mcp-atlassian>=0.1.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.27.0",
    "pydantic>=2.6.0",
    "httpx>=0.27.0",
    "redis>=5.0.0",
    "asyncpg>=0.29.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.2.0",
    "mypy>=1.8.0",
]
```

---

## Appendix B: Environment Setup

```bash
# Quick start commands
git clone <repository>
cd resilix

# Install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run development server
uvicorn main:app --reload

# Run tests
pytest

# Build and run with Docker
docker-compose up --build
```

---

## Appendix C: Hackathon Checklist

- [ ] **Code Repository**: Public GitHub repo with clean README
- [ ] **Working Demo**: Publicly accessible (or AI Studio link)
- [ ] **Video**: 3 minutes max, uploaded to YouTube, English audio/subtitles
- [ ] **Description**: ~200 words explaining Gemini 3 feature usage
- [ ] **Gemini 3 Integration**: Clearly documented which features are used
- [ ] **Not Discouraged Types**: Verified not a simple chatbot/RAG/wrapper

---

*Document Version: 1.1*  
*Last Updated: February 2, 2026*  
*Author: Resilix Team*

---

## Changelog

### Version 1.1 (February 2, 2026)

- **Section 4**: Revised to hybrid agent architecture (2 LLM + 2 deterministic)
- **Section 5**: Updated to Gemini 3 Flash only (removed Pro references)
- **Section 9**: Added `/incidents/{id}/approve-merge` endpoint and response schemas
- **Section 10**: Added `ApprovalStatus`, `PRStatus`, `IncidentStatus`, `IncidentSummary`, `IncidentDetailResponse` models
- **Section 11**: Updated project structure with `frontend/` and `simulator/` directories
- **Section 12**: Replaced with Cloud Run deployment topology and Cloud Build CI/CD
- **Section 14**: Replaced with DNS misconfiguration demo scenario
- **Section 15**: Reordered implementation phases (backend-first approach)
- **Section 16**: Added Frontend Architecture section
