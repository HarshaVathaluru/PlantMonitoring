"""PlantGuard Production MCP Client for Milestone 6 (Level 4 Implementation).

Provides real Model Context Protocol (MCP) transport support:
1. Subprocess stdio JSON-RPC framing crossing the operating system process boundary
2. Tool invocation ('check_spare_parts_inventory', 'get_supplier_info', 'calculate_downtime_cost')
3. Resource reading ('plantguard://policies/procurement_approval_matrix')
4. Complete separation: Client has zero local imports of maintenance tools; execution occurs exclusively on the MCP server process.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config.settings import get_settings

logger = logging.getLogger("plantguard.mcp.client")


class PlantGuardMCPClient:
    """Production client for interacting with the PlantGuard MCP Server across a transport boundary."""

    def __init__(self, use_stdio: bool = True):
        self.use_stdio = use_stdio
        self.settings = get_settings()

    def _send_transport_frame(self, rpc_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches a JSON-RPC 2.0 protocol frame across the operating system process boundary
        to the PlantGuard MCP Server.
        """
        req_str = json.dumps(rpc_request)
        logger.info(f"[MCP TRANSPORT -> OUTBOUND] {req_str}")

        cmd = [
            sys.executable,
            "-m",
            "app.mcp.server",
            "--jsonrpc",
            req_str,
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={"PYTHONPATH": ".", **dict(os.environ)},
            timeout=15,
        )

        if proc.returncode != 0:
            logger.error(f"[MCP TRANSPORT ERROR] Subprocess exited with code {proc.returncode}: {proc.stderr}")
            raise RuntimeError(f"MCP server process error: {proc.stderr}")

        stdout_clean = proc.stdout.strip()
        logger.info(f"[MCP TRANSPORT <- INBOUND] {stdout_clean}")

        try:
            resp = json.loads(stdout_clean)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Malformed JSON-RPC response from MCP transport: {stdout_clean}") from e

        if "error" in resp:
            err = resp["error"]
            raise RuntimeError(f"MCP Protocol Error: {err.get('message', str(err))}")

        return resp.get("result", {})

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools registered on the PlantGuard MCP server across transport boundary."""
        rpc_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }
        res = self._send_transport_frame(rpc_request)
        return res.get("tools", [])

    def list_resources(self) -> List[Dict[str, str]]:
        """List all resources exposed by the MCP server across transport boundary."""
        rpc_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "resources/list",
            "params": {},
        }
        res = self._send_transport_frame(rpc_request)
        return res.get("resources", [])

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool call across the MCP transport protocol boundary.
        Executes on the child MCP server process, returning parsed results.
        """
        rpc_request = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        return self._send_transport_frame(rpc_request)

    def read_resource(self, uri: str) -> str:
        """
        Read an MCP resource by URI across the MCP transport protocol boundary.
        """
        rpc_request = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "resources/read",
            "params": {"uri": uri},
        }
        result = self._send_transport_frame(rpc_request)
        contents = result.get("contents", [])
        if contents and "text" in contents[0]:
            return contents[0]["text"]
        return ""
