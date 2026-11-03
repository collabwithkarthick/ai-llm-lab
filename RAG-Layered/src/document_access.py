"""Demo access rules for documents indexed in Qdrant."""

DOCUMENT_GROUPS = {
    "Employee_Broadband_Expense_Claim_Policy_v3.pdf": ("employees",),
    "IT_Enterprise_Laptop_Upgradation_Policy_v3.pdf": ("it",),
    "IT_Hardware_and_Broadband_Claim_SOP_Guide_v3.pdf": ("it",),
}

KNOWN_GROUPS = frozenset(group for groups in DOCUMENT_GROUPS.values() for group in groups)


def groups_for_document(file_name: str) -> tuple[str, ...]:
    """Return configured access groups, failing closed for unmapped documents."""
    try:
        return DOCUMENT_GROUPS[file_name]
    except KeyError as exc:
        raise ValueError(
            f"No access groups configured for '{file_name}'. "
            "Add it to DOCUMENT_GROUPS before ingestion."
        ) from exc
