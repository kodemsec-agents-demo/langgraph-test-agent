# LangGraph Test Agent

A test agent built with [LangGraph](https://github.com/langchain-ai/langgraph) (ReAct pattern) and FastAPI, designed to run unmanaged on Kubernetes.

## Tools

| Tool | Description |
|------|-------------|
| `system_info` | Hostname, platform, Python version, current time |
| `check_connectivity` | TCP connection test to host:port |
| `http_get` | HTTP GET with response preview |
| `list_env_vars` | List env var names (values redacted) |
| `dns_lookup` | DNS resolution |
| `echo` | Simple echo for tool-call verification |
| `run_diagnostics` | Runs all checks in one shot |

## Run locally

```bash
pip install -r requirements.txt
export AWS_REGION=us-east-1
uvicorn main:app --port 8080
```

## Deploy to Kubernetes

```bash
# Build and push the image
docker build -t <your-registry>/langgraph-test-agent:latest .
docker push <your-registry>/langgraph-test-agent:latest

# Update the image in k8s/deployment.yaml, set the IAM role ARN, then:
kubectl apply -f k8s/deployment.yaml
```

## Invoke

```bash
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Run a full diagnostic check"}'
```

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `MODEL_ID` | `us.anthropic.claude-sonnet-4-20250514` | Bedrock model ID |
| `AWS_REGION` | `us-east-1` | AWS region for Bedrock |
