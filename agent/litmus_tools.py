import os
import requests
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

CHAOS_CENTER_ENDPOINT = 'http://localhost:9091'
LITMUS_PROJECT_ID="3404f946-8ee0-4d9a-9269-7cf38b8b50b4"
LITMUS_ACCESS_TOKEN="eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODE2Njc2ODEsInJvbGUiOiJhZG1pbiIsInVpZCI6ImE2NmNkYWQ2LWMxY2YtNDc0Zi1iOGZmLTE2YzFjNThjZmJmZiIsInVzZXJuYW1lIjoiYWRtaW4ifQ.9pA8ysmnBYafLQGu9L6jVT8Dr5_cy1ubmX57vGSbSITWsZKw712GrG2qAQWNG-sn5LtYGBwAau5L-6p4std3gg"

print('CHAOS_CENTER_ENDPOINT ', CHAOS_CENTER_ENDPOINT)
def get_headers():
    headers = {"Content-Type": "application/json"}
    if LITMUS_ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {LITMUS_ACCESS_TOKEN}"
    return headers

@tool
def check_chaos_center_health() -> str:
    """Checks if the Chaos Center API is reachable and healthy."""
    # This might differ based on actual Litmus version, but we try a basic request
    try:
        # Just knocking on the base URL or API URL
        response = requests.get(f"{CHAOS_CENTER_ENDPOINT}/auth/status", headers=get_headers(), timeout=5)
        if response.status_code == 200:
            return "Chaos Center is reachable and healthy."
        else:
            return f"Chaos Center responded with status code: {response.status_code}"
    except Exception as e:
        return f"Failed to connect to Chaos Center: {str(e)}"

@tool
def query_litmus_graphql(query: str, variables: dict = None) -> str:
    """
    Executes a raw GraphQL query against the Litmus Chaos Center.
    Use this to fetch experiments, workflows, or execute mutations if you know the schema.
    
    Args:
        query: The GraphQL query string.
        variables: Optional variables dictionary for the GraphQL query.
    """
    url = f"{CHAOS_CENTER_ENDPOINT}/api/query"
    payload = {"query": "query ListExperiment($projectID: ID!, $request: ListExperimentRequest!) { totalNoOfExperiments experiments { projectID experimentID }}}"}
    payload["variables"] = variables
        
    try:
        response = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        return f"GraphQL query failed: {str(e)}"

@tool
def list_chaos_experiments() -> str:
    """
    Lists the available chaos experiments/workflows for the current Litmus Project.
    """
    # Example GraphQL query for listing workflows. The schema might vary.
    query = """
    query listChaosWorkflows($request: ListWorkflowRequest!) {
      listWorkflow(request: $request) {
        workflows {
          workflowID
          workflowName
          cronSyntax
          isCustomWorkflow
          updatedAt
        }
      }
    }
    """
    variables = {
        "request": {
            "projectID": LITMUS_PROJECT_ID,
            "filter": {}
        }
    }
    return query_litmus_graphql.invoke({"query": query, "variables": variables})

LITMUS_TOOLS = [
    check_chaos_center_health,
    query_litmus_graphql,
    list_chaos_experiments
]
