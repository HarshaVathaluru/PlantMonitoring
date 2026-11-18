"""Tests for Milestone 6: FastMCP Server, Tools, Resources & Stdio Transport."""
import pytest
from app.mcp.client import PlantGuardMCPClient
from app.mcp.server import mcp_server


def test_mcp_client_list_tools():
    client = PlantGuardMCPClient()
    tools = client.list_tools()
    tool_names = [t["name"] for t in tools]
    assert "check_spare_parts_inventory" in tool_names
    assert "get_supplier_info" in tool_names
    assert "calculate_downtime_cost" in tool_names


def test_mcp_tool_inventory_check():
    client = PlantGuardMCPClient()
    res = client.call_tool("check_spare_parts_inventory", {"part_number": "VPW-P-00000"})
    assert res["part_number"] == "VPW-P-00000"
    assert res["on_hand"] >= 0
    assert res["unit_cost_inr"] > 0
    assert res["supplier_tier"] in ["T1", "T2", "T3", "TIER_1", "TIER_2", "TIER_3"]


def test_mcp_tool_supplier_info():
    client = PlantGuardMCPClient()
    # Supplier SUP-001 is a registered vendor
    res = client.call_tool("get_supplier_info", {"supplier_id": "SUP-001"})
    assert res["status"] == "ACTIVE"
    assert "SUP-001" in res["supplier_id"]
    assert "name" in res


def test_mcp_tool_downtime_calculator():
    client = PlantGuardMCPClient()
    res = client.call_tool("calculate_downtime_cost", {"asset_tag": "VPW-HYD-PRESS-02", "downtime_minutes": 60})
    assert res["asset_tag"] == "VPW-HYD-PRESS-02"
    assert res["total_cost_inr"] == 40000
    assert res["rate_source"] == "asset_specific"


def test_mcp_resource_procurement_matrix():
    client = PlantGuardMCPClient()
    resources = client.list_resources()
    assert len(resources) > 0
    uri = resources[0]["uri"]
    assert uri == "plantguard://policies/procurement_approval_matrix"

    content = client.read_resource(uri)
    assert "PlantGuard Authoritative Procurement Approval Matrix" in content
    assert "200,000" in content
    assert "1,000,000" in content
    assert "Maintenance Manager" in content
    assert "Plant Head" in content
