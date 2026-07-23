"""FastMCP server — embedded MCP tools for AI model consumption.

The server runs in-process with the FastAPI app (stdio mode).
Future Fases may extract it into a sidecar SSE container.

Domain tools (get_products, get_customer, check_eligibility,
simulate_credit, get_insurance) are registered by importing
the domain_tools module.
"""

from fastmcp import FastMCP

mcp = FastMCP("Proteccion360")


@mcp.tool()
def hello_world(name: str = "Mundo") -> str:
    """Saluda a un usuario.

    Parameters
    ----------
    name : str
        Nombre del usuario a saludar (default: "Mundo").

    Returns
    -------
    str
        Saludo personalizado en español.
    """
    return f"Hola, {name}! Bienvenido a Protección Inteligente 360°"


# Import domain tools to register them via the @mcp.tool() decorator
from app.tools import domain_tools  # noqa: E402, F401
