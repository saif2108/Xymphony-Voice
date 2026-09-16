"""Deterministic Customer / CRM Lookup tool."""

from __future__ import annotations

from typing import Any

from xymphony_tools.domain import Tool

_DEFAULT_CUSTOMERS = [
    {
        "id": "cust_101",
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "phone": "+1-555-0101",
        "status": "active",
        "plan": "enterprise",
        "balance_due": 0.0,
        "currency": "USD",
    },
    {
        "id": "cust_102",
        "name": "Bob Smith",
        "email": "bob@example.com",
        "phone": "+1-555-0102",
        "status": "active",
        "plan": "pro",
        "balance_due": 49.99,
        "currency": "USD",
    },
    {
        "id": "cust_103",
        "name": "Carol Williams",
        "email": "carol@example.com",
        "phone": "+1-555-0103",
        "status": "past_due",
        "plan": "starter",
        "balance_due": 15.00,
        "currency": "USD",
    },
]


def lookup_customer(
    query: str,
    lookup_by: str | None = None,
    *,
    customers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Look up a customer record by ID, email, or phone number."""
    search_list = customers if customers is not None else _DEFAULT_CUSTOMERS
    clean_query = query.strip().lower()

    for customer in search_list:
        if lookup_by == "id" and customer["id"].lower() == clean_query:
            return {"found": True, "customer": customer}
        if lookup_by == "email" and customer["email"].lower() == clean_query:
            return {"found": True, "customer": customer}
        if lookup_by == "phone" and customer["phone"].replace(" ", "").replace("-", "") == clean_query.replace(" ", "").replace("-", ""):
            return {"found": True, "customer": customer}

        # Auto-match across any identifier if lookup_by is not specified
        if lookup_by is None:
            if customer["id"].lower() == clean_query:
                return {"found": True, "customer": customer}
            if customer["email"].lower() == clean_query:
                return {"found": True, "customer": customer}
            if customer["phone"].replace(" ", "").replace("-", "") == clean_query.replace(" ", "").replace("-", ""):
                return {"found": True, "customer": customer}

    return {
        "found": False,
        "message": f"Customer not found for query: '{query}'",
    }


def create_customer_lookup_tool(customers: list[dict[str, Any]] | None = None) -> Tool:
    """Create a configured Tool instance for customer CRM lookup."""

    def _handler(query: str, lookup_by: str | None = None) -> dict[str, Any]:
        return lookup_customer(query, lookup_by, customers=customers)

    return Tool(
        name="customer_lookup",
        description="Looks up customer profile, account details, and subscription status by customer ID, email, or phone number.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Identifier to search for (e.g., customer ID, email address, or phone number).",
                },
                "lookup_by": {
                    "type": "string",
                    "enum": ["id", "email", "phone"],
                    "description": "Explicit identifier field to search. Defaults to searching all identifiers.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_handler,
    )
