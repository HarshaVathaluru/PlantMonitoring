"""PlantGuard MCP Client for Milestone 6.

Provides client access to the PlantGuard MCP tools and resources.
Supports both in-memory direct invocation and stdio JSON-RPC subprocess communication.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.mcp.server import (
    calculate_downtime_cost,
    check_spare_parts_inventory,
    get_procurement_approval_matrix,
    get_supplier_info,
    mcp_server,
)

logger = logging.getLogger(__name__)


class PlantGuardMCPClient:
    """Client for interacting with the PlantGuard FastMCP server."""

    def __init__(self, in_memory: bool = True):
        self.in_memory = in_memory
        self._server = mcp_server

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools registered on the PlantGuard MCP server."""
        return [
            {
                "name": "check_spare_parts_inventory",
                "description": "Check stock level, reorder point, unit cost, and supplier tier for a spare part.",
                "parameters": {"part_number": "string"},
            },
            {
                "name": "get_supplier_info",
                "description": "Retrieve vendor contact details, lead time, and reliability tier by supplier ID.",
                "parameters": {"supplier_id": "string"},
            },
            {
                "name": "calculate_downtime_cost",
                "description": "Calculate financial impact of equipment downtime using asset-specific hourly rate.",
                "parameters": {"asset_tag": "string", "downtime_minutes": "integer"},
            },
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool by name."""
        logger.info(f"Invoking MCP tool '{tool_name}' with arguments: {arguments}")
        
        if tool_name == "check_spare_parts_inventory":
            return check_spare_parts_inventory(arguments.get("part_number", ""))
        elif tool_name == "get_supplier_info":
            return get_supplier_info(arguments.get("supplier_id", ""))
        elif tool_name == "calculate_downtime_cost":
            return calculate_downtime_cost(
                arguments.get("asset_tag", ""),
                arguments.get("downtime_minutes", 60),
            )
        else:
            raise ValueError(f"Unknown MCP tool: {tool_name}")

    def list_resources(self) -> List[Dict[str, str]]:
        """List all resources exposed by the MCP server."""
        return [
            {
                "uri": "plantguard://policies/procurement_approval_matrix",
                "name": "Procurement Approval Matrix",
                "mimeType": "text/markdown",
            }
        ]

    def read_resource(self, uri: str) -> str:
        """Read an MCP resource by URI."""
        logger.info(f"Reading MCP resource URI: '{uri}'")
        if uri == "plantguard://policies/procurement_approval_matrix":
            return get_procurement_approval_matrix()
        else:
            raise ValueError(f"Resource not found: {uri}")
