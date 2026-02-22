from typing import Dict, List, Optional, Union
import msal


def acquire_token_ccf(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    scope: Union[str, List[str]],
) -> Dict:
    """Acquire a token using the client credentials flow (CCF).

    Args:
        tenant_id: Azure AD tenant ID (GUID or tenant name)
        client_id: Application (client) ID
        client_secret: Client secret for the application
        scope: Resource scope or list of scopes (e.g. "https://graph.microsoft.com/.default")
        user_assertion: Ignored for CCF but accepted for API consistency

    Returns:
        The raw token response dict from MSAL. On success it contains ``access_token``.

    Raises:
        RuntimeError: if token acquisition fails.
    """
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id, client_credential=client_secret, authority=authority
    )

    token = app.acquire_token_for_client(scopes=[scope] if isinstance(scope, str) else scope)

    if token and "access_token" in token:
        return token

    error = token or {}
    raise RuntimeError(
        f"CCF token acquisition failed: {error.get('error')} - {error.get('error_description')}"
    )


def acquire_token_obo(
    tenant_id: str,
    client_id: str,
    client_secret: str,
    scope: List[str],
    user_assertion: Optional[str] = None,
) -> Dict:
    """Acquire a token using the On-Behalf-Of (OBO) flow.

    Args:
        tenant_id: Azure AD tenant ID (GUID or tenant name)
        client_id: Application (client) ID
        client_secret: Client secret for the application
        scope: Resource scope or list of scopes (e.g. ["https://graph.microsoft.com/.default"]) 
        user_assertion: The incoming user assertion (JWT) to exchange for a delegated token

    Returns:
        The raw token response dict from MSAL. On success it contains ``access_token``.

    Raises:
        ValueError: if `user_assertion` is not provided.
        RuntimeError: if token acquisition fails.
    """
    if not user_assertion:
        raise ValueError("`user_assertion` is required for the OBO flow")

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id, client_credential=client_secret, authority=authority
    )

    token = app.acquire_token_on_behalf_of(user_assertion, scopes=[scope] if isinstance(scope, str) else scope)

    if token and "access_token" in token:
        return token

    error = token or {}
    raise RuntimeError(
        f"OBO token acquisition failed: {error.get('error')} - {error.get('error_description')}"
    )


__all__ = [
    "acquire_token_ccf",
    "acquire_token_obo",
]
