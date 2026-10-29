import datetime
import os
import platform
import socket
import urllib.request
from typing import Annotated

import boto3
from fastapi import FastAPI, Request
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

SYSTEM_PROMPT = """You are a test agent deployed on Kubernetes.
Your purpose is to help verify that agent infrastructure is working correctly.
You have several diagnostic tools available. Use them when asked to check
system health, network connectivity, or environment details."""

app = FastAPI(title="langgraph-test-agent")


@tool
def system_info() -> dict:
    """Return basic system information: hostname, platform, Python version, current time."""
    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "utc_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pid": os.getpid(),
        "cwd": os.getcwd(),
    }


@tool
def check_connectivity(
    host: Annotated[str, "The hostname or IP to connect to"],
    port: Annotated[int, "The port number"] = 443,
    timeout: Annotated[int, "Connection timeout in seconds"] = 5,
) -> dict:
    """Check TCP connectivity to a host and port."""
    try:
        start = datetime.datetime.now(datetime.timezone.utc)
        sock = socket.create_connection((host, port), timeout=timeout)
        elapsed = (datetime.datetime.now(datetime.timezone.utc) - start).total_seconds()
        sock.close()
        return {"host": host, "port": port, "reachable": True, "latency_seconds": round(elapsed, 3)}
    except Exception as e:
        return {"host": host, "port": port, "reachable": False, "error": str(e)}


@tool
def http_get(
    url: Annotated[str, "The URL to fetch"],
    timeout: Annotated[int, "Request timeout in seconds"] = 10,
) -> dict:
    """Perform an HTTP GET request and return the status code and a preview of the body."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "test-agent/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(2048).decode("utf-8", errors="replace")
            return {"url": url, "status": resp.status, "body_preview": body[:500]}
    except Exception as e:
        return {"url": url, "error": str(e)}


@tool
def list_env_vars(
    prefix: Annotated[str, "Only show variables starting with this prefix"] = "",
) -> dict:
    """List environment variable names, optionally filtered by prefix. Values are redacted."""
    matching = sorted(k for k in os.environ if k.startswith(prefix)) if prefix else sorted(os.environ)
    return {"count": len(matching), "variables": matching}


@tool
def dns_lookup(hostname: Annotated[str, "The hostname to resolve"]) -> dict:
    """Resolve a hostname to its IP addresses."""
    try:
        results = socket.getaddrinfo(hostname, None)
        ips = sorted(set(r[4][0] for r in results))
        return {"hostname": hostname, "addresses": ips}
    except Exception as e:
        return {"hostname": hostname, "error": str(e)}


@tool
def echo(message: Annotated[str, "The message to echo back"]) -> str:
    """Echo a message back. Useful as a no-op test to verify tool calling works."""
    return f"Echo: {message}"


@tool
def run_diagnostics() -> dict:
    """Run a full suite of diagnostic checks: system info, DNS, connectivity to common endpoints."""
    checks = {}
    checks["system"] = system_info.invoke({})
    checks["dns_aws"] = dns_lookup.invoke({"hostname": "bedrock-runtime.us-east-1.amazonaws.com"})
    checks["dns_google"] = dns_lookup.invoke({"hostname": "www.google.com"})
    checks["tcp_aws"] = check_connectivity.invoke({"host": "bedrock-runtime.us-east-1.amazonaws.com", "port": 443})
    checks["tcp_google"] = check_connectivity.invoke({"host": "www.google.com", "port": 443})
    checks["env_summary"] = {"total_vars": len(os.environ)}
    return checks


TOOLS = [system_info, check_connectivity, http_get, list_env_vars, dns_lookup, echo, run_diagnostics]


def create_agent():
    model = ChatBedrockConverse(
        model_id=MODEL_ID,
        region_name=AWS_REGION,
        max_tokens=4096,
    )
    return create_react_agent(model, TOOLS)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/invoke")
async def invoke(request: Request):
    body = await request.json()
    prompt = body.get("prompt", body.get("messages", ""))
    if isinstance(prompt, list):
        prompt = "\n".join(m.get("content", "") for m in prompt if isinstance(m, dict))

    agent = create_agent()
    result = agent.invoke(
        {"messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]}
    )
    last_message = result["messages"][-1]
    return {"response": last_message.content}
