# Model Context Protocol (MCP) Guide

## Overview

The Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). It creates a consistent interface between AI models and various data sources/tools, similar to how USB-C provides a standardized way to connect devices to peripherals.

## Core Architecture

MCP follows a client-server architecture:

- **MCP Hosts**: Programs like Claude Desktop, IDEs, or AI tools that want to access data through MCP
- **MCP Clients**: Protocol clients that maintain 1:1 connections with servers
- **MCP Servers**: Lightweight programs that expose capabilities through the standardized protocol
- **Local Data Sources**: Your computer's files, databases, and services that MCP servers can securely access
- **Remote Services**: External systems available over the internet (APIs) that MCP servers can connect to

## Core Primitives

MCP defines three primary primitives:

| Primitive | Control | Description | Example Use |
| --- | --- | --- | --- |
| **Resources** | Application-controlled | Contextual data managed by the client | File contents, API responses |
| **Tools** | Model-controlled | Functions exposed to the LLM to take actions | API calls, data processing |
| **Prompts** | User-controlled | Interactive templates invoked by user choice | Slash commands, menu options |

## Building an MCP Server with Python

### Installation

```bash
pip install mcp
# or with CLI tools
pip install "mcp[cli]"
```

### Quickstart Example

```python
# server.py
from mcp.server.fastmcp import FastMCP

# Create an MCP server
mcp = FastMCP("Demo")

# Add a tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

# Add a dynamic resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"
```

### Running Your Server

**Development Mode:**
```bash
mcp dev server.py
```

**Claude Desktop Integration:**
```bash
mcp install server.py
```

**Direct Execution:**
```python
if __name__ == "__main__":
    mcp.run()
```

## Implementing Server Features

### Resources

Resources expose data to LLMs (similar to GET endpoints):

```python
# Static resource
@mcp.resource("config://app")
def get_config() -> str:
    """Static configuration data"""
    return "App configuration here"

# Dynamic resource with parameters
@mcp.resource("users://{user_id}/profile")
def get_user_profile(user_id: str) -> str:
    """Dynamic user data"""
    return f"Profile data for user {user_id}"
```

### Tools

Tools let LLMs take actions through your server:

```python
# Simple synchronous tool
@mcp.tool()
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """Calculate BMI given weight in kg and height in meters"""
    return weight_kg / (height_m ** 2)

# Asynchronous tool
@mcp.tool()
async def fetch_weather(city: str) -> str:
    """Fetch current weather for a city"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.weather.com/{city}")
        return response.text
```

### Prompts

Prompts are reusable templates for LLM interactions:

```python
# Simple prompt returning a string
@mcp.prompt()
def review_code(code: str) -> str:
    return f"Please review this code:\n\n{code}"

# More complex prompt with message structure
@mcp.prompt()
def debug_error(error: str) -> list[Message]:
    return [
        UserMessage("I'm seeing this error:"),
        UserMessage(error),
        AssistantMessage("I'll help debug that. What have you tried so far?")
    ]
```

### Working with Images

```python
from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage

@mcp.tool()
def create_thumbnail(image_path: str) -> Image:
    """Create a thumbnail from an image"""
    img = PILImage.open(image_path)
    img.thumbnail((100, 100))
    return Image(data=img.tobytes(), format="png")
```

### Context and Progress Tracking

```python
@mcp.tool()
async def long_task(files: list[str], ctx: Context) -> str:
    """Process multiple files with progress tracking"""
    for i, file in enumerate(files):
        ctx.info(f"Processing {file}")
        await ctx.report_progress(i, len(files))
        data, mime_type = await ctx.read_resource(f"file://{file}")
    return "Processing complete"
```

## Advanced Server Setup

### Application Lifecycle Management

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP

@dataclass
class AppContext:
    db: Database  # Replace with your actual DB type

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    try:
        # Initialize on startup
        await db.connect()
        yield AppContext(db=db)
    finally:
        # Cleanup on shutdown
        await db.disconnect()

# Pass lifespan to server
mcp = FastMCP("My App", lifespan=app_lifespan)

# Access type-safe lifespan context in tools
@mcp.tool()
def query_db(ctx: Context) -> str:
    """Tool that uses initialized resources"""
    db = ctx.request_context.lifespan_context["db"]
    return db.query()
```

### Example Servers

#### Echo Server
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Echo")

@mcp.resource("echo://{message}")
def echo_resource(message: str) -> str:
    """Echo a message as a resource"""
    return f"Resource echo: {message}"

@mcp.tool()
def echo_tool(message: str) -> str:
    """Echo a message as a tool"""
    return f"Tool echo: {message}"

@mcp.prompt()
def echo_prompt(message: str) -> str:
    """Create an echo prompt"""
    return f"Please process this message: {message}"
```

#### SQLite Explorer
```python
from mcp.server.fastmcp import FastMCP
import sqlite3

mcp = FastMCP("SQLite Explorer")

@mcp.resource("schema://main")
def get_schema() -> str:
    """Provide the database schema as a resource"""
    conn = sqlite3.connect("database.db")
    schema = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return "\n".join(sql[0] for sql in schema if sql[0])

@mcp.tool()
def query_data(sql: str) -> str:
    """Execute SQL queries safely"""
    conn = sqlite3.connect("database.db")
    try:
        result = conn.execute(sql).fetchall()
        return "\n".join(str(row) for row in result)
    except Exception as e:
        return f"Error: {str(e)}"
```

## References

For more information about MCP:

- **Protocol Documentation**: [https://modelcontextprotocol.io/](https://modelcontextprotocol.io/)
- **Specification**: [https://spec.modelcontextprotocol.io/](https://spec.modelcontextprotocol.io/)
- **GitHub Repositories**:
  - Protocol Specification: [https://github.com/modelcontextprotocol/specification](https://github.com/modelcontextprotocol/specification)
  - Python SDK: [https://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)

These resources can be accessed using the `fetch` tool in compatible AI models.