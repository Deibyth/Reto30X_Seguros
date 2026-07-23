"""Tests for the ToolBridge service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.tool_bridge import ToolBridge


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


from app.services.tool_bridge import TOOL_DOMAINS


@pytest.fixture
def mock_tools():
    """Return two tool definitions: save_form_field (with session_id) and get_products.

    Each tool gets a domain tag via a metadata dict attribute.
    """
    save_form = MagicMock()
    save_form.name = "save_form_field"
    save_form.description = "Save a single collected form field"
    save_form.parameters = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string", "description": "The active session UUID"},
            "campo": {"type": "string", "description": "Field name"},
            "valor": {"type": "string", "description": "Field value"},
        },
        "required": ["session_id", "campo"],
    }

    get_products = MagicMock()
    get_products.name = "get_products"
    get_products.description = "List available products"
    get_products.parameters = {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "description": "Filter by type"},
        },
        "required": [],
    }

    return [save_form, get_products]


@pytest.fixture
def mock_mcp(mock_tools):
    """FastMCP instance with controlled list_tools / call_tool."""
    mcp = MagicMock()
    mcp.list_tools = AsyncMock(return_value=mock_tools)
    mcp.call_tool = AsyncMock()
    return mcp


@pytest.fixture
def bridge(mock_mcp):
    """ToolBridge wired to the mock MCP."""
    return ToolBridge(mock_mcp)


# ---------------------------------------------------------------------------
# get_openai_tools
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_openai_tools_returns_list(bridge):
    """get_openai_tools should return a list of tool definitions."""
    tools = await bridge.get_openai_tools()
    assert isinstance(tools, list)
    assert len(tools) == 2


@pytest.mark.asyncio
async def test_get_openai_tools_strips_session_id(bridge):
    """get_openai_tools should strip session_id from save_form_field schema."""
    tools = await bridge.get_openai_tools()

    save_form = next(
        t for t in tools if t["function"]["name"] == "save_form_field"
    )
    params = save_form["function"]["parameters"]
    props = params["properties"]
    required = params["required"]

    assert "session_id" not in props
    assert "session_id" not in required
    assert "campo" in props
    assert "valor" in props


@pytest.mark.asyncio
async def test_get_openai_tools_other_tools_unaffected(bridge):
    """get_openai_tools should NOT strip params from tools without HIDDEN_PARAMS."""
    tools = await bridge.get_openai_tools()

    get_prods = next(
        t for t in tools if t["function"]["name"] == "get_products"
    )
    params = get_prods["function"]["parameters"]
    props = params["properties"]

    assert "tipo" in props
    assert len(props) == 1  # only tipo, no session_id tampering


# ---------------------------------------------------------------------------
# execute_tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_tool_injects_session_id(bridge, mock_mcp):
    """execute_tool should inject session_id before calling MCP for save_form_field."""
    mock_mcp.call_tool.return_value = MagicMock(
        content=[MagicMock(text="ok")]
    )
    bridge.current_session_id = "ses-abc"

    result = await bridge.execute_tool(
        "save_form_field",
        {"campo": "nombres", "valor": "Juan"},
    )

    assert result == "ok"
    # Verify the MCP was called with session_id injected
    call_args = mock_mcp.call_tool.call_args
    assert call_args[0][0] == "save_form_field"
    injected = call_args[0][1]
    assert injected["session_id"] == "ses-abc"
    assert injected["campo"] == "nombres"


@pytest.mark.asyncio
async def test_execute_tool_unknown_raises_value_error(bridge):
    """execute_tool should raise ValueError for an unknown tool name."""
    with pytest.raises(ValueError, match="Unknown tool"):
        await bridge.execute_tool("nonexistent_tool", {})


# ---------------------------------------------------------------------------
# Domain tool filtering (Task 3.2)
# ---------------------------------------------------------------------------


@pytest.fixture
def domain_tools_fixture():
    """Four mock MCP tools with domain metadata: 2 credit, 2 insurance."""
    tools = []
    for name, domain in [
        ("get_products", "credit"),
        ("simulate_credit", "credit"),
        ("recommend_insurance", "insurance"),
        ("quote_insurance", "insurance"),
    ]:
        t = MagicMock()
        t.name = name
        t.description = f"Tool {name}"
        t.parameters = {
            "type": "object",
            "properties": {"dummy": {"type": "string"}},
            "required": [],
        }
        tools.append(t)

    mcp = MagicMock()
    mcp.list_tools = AsyncMock(return_value=tools)
    mcp.call_tool = AsyncMock(
        return_value=MagicMock(content=[MagicMock(text="ok")])
    )
    return mcp


@pytest.mark.asyncio
async def test_get_openai_tools_no_domain_returns_all(domain_tools_fixture):
    """With domain=None, get_openai_tools returns all tools."""
    bridge = ToolBridge(domain_tools_fixture)
    result = await bridge.get_openai_tools()
    assert len(result) == 4


@pytest.mark.asyncio
async def test_get_openai_tools_credit_domain(domain_tools_fixture):
    """With domain='credit', get_openai_tools returns only credit-tagged tools."""
    bridge = ToolBridge(domain_tools_fixture)
    result = await bridge.get_openai_tools(domain="credit")
    names = [t["function"]["name"] for t in result]
    assert "get_products" in names
    assert "simulate_credit" in names
    assert "recommend_insurance" not in names
    assert "quote_insurance" not in names
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_openai_tools_insurance_domain(domain_tools_fixture):
    """With domain='insurance', get_openai_tools returns only insurance-tagged tools."""
    bridge = ToolBridge(domain_tools_fixture)
    result = await bridge.get_openai_tools(domain="insurance")
    names = [t["function"]["name"] for t in result]
    assert "recommend_insurance" in names
    assert "quote_insurance" in names
    assert "get_products" not in names
    assert "simulate_credit" not in names
    assert len(result) == 2
