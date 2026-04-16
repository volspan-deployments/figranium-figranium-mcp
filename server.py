from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
import threading
from fastmcp import FastMCP
import httpx
import os
import subprocess
import sys
from typing import Optional

mcp = FastMCP("Figranium")

BASE_URL = "http://localhost:11345"
API_KEY = os.environ.get("SESSION_SECRET", "")


def get_headers():
    return {
        "x-api-key": API_KEY,
        "Content-Type": "application/json",
    }


def build_figranium_cmd(args: list) -> list:
    """Build a figranium CLI command."""
    return ["npx", "figranium"] + args


@mcp.tool()
async def start_dashboard(port: Optional[int] = 11345) -> dict:
    """Start the Figranium web dashboard server. Use this when the user wants to launch the local web UI to manage tasks, view captures, configure proxies, or access the full browser automation control plane. Optionally specify a custom port."""
    try:
        cmd = build_figranium_cmd(["--port", str(port)])
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PORT": str(port)},
        )
        # Give it a moment to start
        import asyncio
        await asyncio.sleep(2)
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            return {
                "success": False,
                "error": "Dashboard process exited early",
                "stdout": stdout,
                "stderr": stderr,
            }
        return {
            "success": True,
            "message": f"Figranium dashboard starting on port {port}",
            "url": f"http://localhost:{port}",
            "pid": process.pid,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "figranium CLI not found. Make sure it is installed via npm/npx.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def run_scrape(
    url: Optional[str] = None,
    selector: Optional[str] = None,
    wait: Optional[int] = None,
    task: Optional[str] = None,
) -> dict:
    """Execute a one-off web scraping task against a target URL using Playwright. Use this when the user wants to extract content from a webpage, optionally targeting specific elements via a CSS selector. Can also run a previously saved scrape task by ID."""
    # Try HTTP API first
    try:
        payload = {}
        if url:
            payload["url"] = url
        if selector:
            payload["selector"] = selector
        if wait is not None:
            payload["wait"] = wait
        if task:
            payload["task"] = task

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/api/scrape",
                json=payload,
                headers=get_headers(),
            )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            # Fall back to CLI if API endpoint doesn't exist
            if response.status_code == 404:
                raise httpx.HTTPStatusError("Not found", request=response.request, response=response)
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
            }
    except (httpx.ConnectError, httpx.HTTPStatusError):
        pass
    except Exception as e:
        pass

    # Fall back to CLI
    try:
        cmd = build_figranium_cmd(["--scrape"])
        if url:
            cmd += ["--url", url]
        if selector:
            cmd += ["--selector", selector]
        if wait is not None:
            cmd += ["--wait", str(wait)]
        if task:
            cmd += ["--task", task]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Scrape task timed out after 120 seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def run_agent(
    url: Optional[str] = None,
    task: Optional[str] = None,
    wait: Optional[int] = None,
) -> dict:
    """Execute a one-off agent task that uses AI-driven browser automation to interact with a webpage. Use this when the user wants to perform complex, multi-step browser interactions such as form filling, clicking, navigation, or executing JavaScript on a page. Can run a saved task by ID or target a new URL."""
    # Try HTTP API first
    try:
        payload = {}
        if url:
            payload["url"] = url
        if task:
            payload["task"] = task
        if wait is not None:
            payload["wait"] = wait

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{BASE_URL}/api/agent",
                json=payload,
                headers=get_headers(),
            )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            if response.status_code == 404:
                raise httpx.HTTPStatusError("Not found", request=response.request, response=response)
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
            }
    except (httpx.ConnectError, httpx.HTTPStatusError):
        pass
    except Exception as e:
        pass

    # Fall back to CLI
    try:
        cmd = build_figranium_cmd(["--agent"])
        if url:
            cmd += ["--url", url]
        if task:
            cmd += ["--task", task]
        if wait is not None:
            cmd += ["--wait", str(wait)]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Agent task timed out after 180 seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def open_headful_browser(
    url: str,
    wait: Optional[int] = None,
) -> dict:
    """Open a visible (headful) browser window pointing to a target URL for manual inspection or interaction. Use this when the user wants to observe what the browser sees, debug a scrape/agent task visually, or manually interact with a site before automating it."""
    # Try HTTP API first
    try:
        payload = {"url": url}
        if wait is not None:
            payload["wait"] = wait

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{BASE_URL}/api/headful",
                json=payload,
                headers=get_headers(),
            )
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            if response.status_code == 404:
                raise httpx.HTTPStatusError("Not found", request=response.request, response=response)
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
            }
    except (httpx.ConnectError, httpx.HTTPStatusError):
        pass
    except Exception as e:
        pass

    # Fall back to CLI
    try:
        cmd = build_figranium_cmd(["--headful", "--url", url])
        if wait is not None:
            cmd += ["--wait", str(wait)]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        import asyncio
        await asyncio.sleep(2)
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            return {
                "success": False,
                "error": "Headful browser process exited early",
                "stdout": stdout,
                "stderr": stderr,
            }
        return {
            "success": True,
            "message": f"Headful browser opened for URL: {url}",
            "pid": process.pid,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def list_tasks() -> dict:
    """Load and list all saved automation tasks from storage. Use this when the user wants to see what scrape, agent, or automation workflows have been configured, to find a task ID, or to audit existing tasks before running or modifying them."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{BASE_URL}/api/tasks",
                headers=get_headers(),
            )
            if response.status_code == 200:
                return {"success": True, "tasks": response.json()}
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
            }
    except httpx.ConnectError:
        return {
            "success": False,
            "error": "Cannot connect to Figranium server at http://localhost:11345. Please start the dashboard first using start_dashboard.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_task(id: str) -> dict:
    """Retrieve the full details of a specific saved task by its ID. Use this when the user wants to inspect a task's configuration, actions, URL, selector, scheduling settings, or other properties before running or editing it."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{BASE_URL}/api/tasks/{id}",
                headers=get_headers(),
            )
            if response.status_code == 200:
                return {"success": True, "task": response.json()}
            if response.status_code == 404:
                return {"success": False, "error": f"Task with ID '{id}' not found."}
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
            }
    except httpx.ConnectError:
        return {
            "success": False,
            "error": "Cannot connect to Figranium server at http://localhost:11345. Please start the dashboard first using start_dashboard.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
async def get_help() -> dict:
    """Display the full Figranium CLI help message including all available commands, flags, options, and environment variable configuration. Use this when the user is unsure what Figranium supports, wants a quick reference, or needs to understand available CLI options."""
    try:
        cmd = build_figranium_cmd(["--help"])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        help_text = result.stdout or result.stderr
        if not help_text.strip():
            help_text = """
Figranium CLI - Deterministic Control for an Agentic World

Usage:
  figranium [options]
  figranium --scrape --url <url> [--selector <css>]
  figranium --agent --task <id>
  figranium --headful --url <url>

Options:
  --scrape              Run a one-off scrape task
  --agent               Run a one-off agent task
  --headful             Open a headful browser session for manual interaction
  --url <url>           Target URL for the task
  --task <id>           Run a saved task by its ID
  --selector <css>      CSS selector for scraping mode
  --wait <seconds>      Seconds to wait after page load
  --port <number>       Port for the web dashboard (default: 11345)
  --help, -h            Show this help message

Environment Variables:
  PORT                  Port for the server
  SESSION_SECRET        Secret for session encryption
  ALLOWED_IPS           Comma-separated list of allowed IPs

Examples:
  figranium                             # Starts web dashboard
  figranium --scrape --url google.com   # Scrapes Google homepage
  figranium --agent --task my-task-123  # Runs saved agent task
"""
        return {
            "success": True,
            "help": help_text,
        }
    except FileNotFoundError:
        return {
            "success": True,
            "help": """
Figranium CLI - Deterministic Control for an Agentic World

Usage:
  figranium [options]
  figranium --scrape --url <url> [--selector <css>]
  figranium --agent --task <id>
  figranium --headful --url <url>

Options:
  --scrape              Run a one-off scrape task
  --agent               Run a one-off agent task
  --headful             Open a headful browser session for manual interaction
  --url <url>           Target URL for the task
  --task <id>           Run a saved task by its ID
  --selector <css>      CSS selector for scraping mode
  --wait <seconds>      Seconds to wait after page load
  --port <number>       Port for the web dashboard (default: 11345)
  --help, -h            Show this help message

Environment Variables:
  PORT                  Port for the server
  SESSION_SECRET        Secret for session encryption
  ALLOWED_IPS           Comma-separated list of allowed IPs

Examples:
  figranium                             # Starts web dashboard
  figranium --scrape --url google.com   # Scrapes Google homepage
  figranium --agent --task my-task-123  # Runs saved agent task

Note: figranium CLI not found in PATH. Install via: npm install -g figranium or use npx figranium.
""",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}




_SERVER_SLUG = "figranium-figranium"

def _track(tool_name: str, ua: str = ""):
    try:
        import urllib.request, json as _json
        data = _json.dumps({"slug": _SERVER_SLUG, "event": "tool_call", "tool": tool_name, "user_agent": ua}).encode()
        req = urllib.request.Request("https://www.volspan.dev/api/analytics/event", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass

async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http", stateless_http=True)

class _FixAcceptHeader:
    """Ensure Accept header includes both types FastMCP requires."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            accept = headers.get(b"accept", b"").decode()
            if "text/event-stream" not in accept:
                new_headers = [(k, v) for k, v in scope["headers"] if k != b"accept"]
                new_headers.append((b"accept", b"application/json, text/event-stream"))
                scope = dict(scope, headers=new_headers)
        await self.app(scope, receive, send)

app = _FixAcceptHeader(Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", mcp_app),
    ],
    lifespan=mcp_app.lifespan,
))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
