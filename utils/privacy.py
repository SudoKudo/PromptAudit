"""Keep credentials out of saved settings and diagnostic messages."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SECRET_KEYS = {
    "key", "token", "secret", "password", "passwd", "credentials", "credential",
    "authorization", "proxyauthorization", "cookie", "cookies", "sessionid",
    "apikey", "accesstoken", "refreshtoken", "authtoken", "bearertoken", "hftoken",
    "clientsecret", "privatekey", "signature", "sig",
}
_SECRET_SUFFIXES = (
    "apikey", "accesstoken", "refreshtoken", "authtoken", "bearertoken", "hftoken",
    "password", "passwd", "clientsecret", "privatekey", "signature",
    "credential", "authorization", "sessiontoken", "securitytoken",
)
_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE)


def _secret_key(key):
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return normalized in _SECRET_KEYS or normalized.endswith(_SECRET_SUFFIXES)


def _safe_url(match):
    original = match.group(0)
    try:
        parts = urlsplit(original)
        netloc = parts.netloc.rsplit("@", 1)[-1]
        query = parse_qsl(parts.query, keep_blank_values=True)
        public_query = [(key, value) for key, value in query if not _secret_key(key)]
        fragment = parse_qsl(parts.fragment, keep_blank_values=True)
        public_fragment = [(key, value) for key, value in fragment if not _secret_key(key)]
        if netloc == parts.netloc and public_query == query and public_fragment == fragment:
            return original
        return urlunsplit((parts.scheme, netloc, parts.path, urlencode(public_query),
                           parts.fragment if public_fragment == fragment else urlencode(public_fragment)))
    except ValueError:
        return "[invalid URL]"


def safe_text(value):
    """Remove bearer tokens and URL credentials from a diagnostic string."""
    return _BEARER.sub("Bearer [REDACTED]", _URL.sub(_safe_url, str(value)))


def safe_settings(value):
    """Return a copy with credential fields omitted, including nested settings."""
    if isinstance(value, dict):
        return {key: safe_settings(item) for key, item in value.items() if not _secret_key(key)}
    if isinstance(value, (list, tuple)):
        return [safe_settings(item) for item in value]
    if isinstance(value, str):
        return safe_text(value)
    return value
