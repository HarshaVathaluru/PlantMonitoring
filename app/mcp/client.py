"""Synchronous facade over the official MCP SDK stdio client."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config.settings import get_settings

logger = logging.getLogger("plantguard.mcp.client")


class PlantGuardMCPClient:
    """Call the PlantGuard MCP server through SDK-managed stdio sessions."""

    def __init__(self, use_stdio: bool = True):
        if not use_stdio:
            raise ValueError("PlantGuard supports the official MCP stdio transport only")
        self.settings = get_settings()
        self.project_root = Path(__file__).resolve().parents[2]
        self.call_log: List[Dict[str, str]] = []

    def _server_parameters(self) -> StdioServerParameters:
        env = dict(os.environ)
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(self.project_root) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.server"],
            cwd=self.project_root,
            env=env,
        )

    async def _request(self, operation: str, *args: Any) -> Any:
        async with stdio_client(self._server_parameters(), errlog=sys.stderr) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await getattr(session, operation)(*args)
                if getattr(result, "isError", False):
                    raise RuntimeError(f"MCP {operation} failed: {result}")
                return result

    def _run(self, operation: str, *args: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._request(operation, *args))
        raise RuntimeError("PlantGuardMCPClient synchronous methods cannot run inside an active event loop")

    @staticmethod
    def _dump(value: Any) -> Dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", by_alias=True, exclude_none=True)
        return dict(value)

    @staticmethod
    def _text_content(result: Any) -> str:
        texts = []
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                texts.append(text)
        return "\n".join(texts)

    def list_tools(self) -> List[Dict[str, Any]]:
        result = self._run("list_tools")
        return [self._dump(tool) for tool in result.tools]

    def list_resources(self) -> List[Dict[str, Any]]:
        result = self._run("list_resources")
        return [self._dump(resource) for resource in result.resources]

    def list_prompts(self) -> List[Dict[str, Any]]:
        result = self._run("list_prompts")
        return [self._dump(prompt) for prompt in result.prompts]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        result = self._run("call_tool", tool_name, arguments)
        content = self._text_content(result)
        if getattr(result, "isError", False) or content.lstrip().lower().startswith(("error:", "unknown tool:")):
            if content.lower().startswith("unknown tool:"):
                content = f"Tool not found: {tool_name}"
            raise RuntimeError(f"MCP tool {tool_name} failed: {content}")
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            self.call_log.append({"operation": "call_tool", "name": tool_name})
            return dict(structured)
        try:
            parsed = json.loads(content)
            self.call_log.append({"operation": "call_tool", "name": tool_name})
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except json.JSONDecodeError:
            self.call_log.append({"operation": "call_tool", "name": tool_name})
            return {"content": content}

    def read_resource(self, uri: str) -> str:
        result = self._run("read_resource", uri)
        self.call_log.append({"operation": "read_resource", "name": uri})
        contents = getattr(result, "contents", []) or []
        return str(getattr(contents[0], "text", "")) if contents else ""

    def get_prompt(self, name: str, arguments: Optional[Dict[str, str]] = None) -> str:
        result = self._run("get_prompt", name, arguments or {})
        self.call_log.append({"operation": "get_prompt", "name": name})
        messages = getattr(result, "messages", []) or []
        if not messages:
            return ""
        content = getattr(messages[0], "content", None)
        return str(getattr(content, "text", ""))
