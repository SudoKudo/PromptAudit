"""Small in-memory sample sets used for smoke tests and demos."""

def load_cvefixes():
    """
    Return a tiny, hard-coded subset shaped like CVEfixes samples.

    Each entry:
        - "id": numeric identifier
        - "code": code snippet (e.g., vulnerable or fixed version)
        - "label": vulnerability label ("VULNERABLE" or "SAFE")
    """
    return [
        # Example of a vulnerable use of strcat (no bounds checking).
        {"id": 1001, "code": "strcat(buf,input);", "label": "VULNERABLE"},

        # Safer alternative using strncat with explicit length limits.
        {"id": 1002, "code": "strncat(buf,input,sizeof(buf)-strlen(buf)-1);", "label": "SAFE"},
    ]


def load_bigvul():
    """
    Return a tiny, hard-coded subset shaped like BigVul samples.

    Note:
        The string literal keeps the "%s" placeholder intact so the example
        still resembles the original C formatting pattern.
    """
    return [
        # Vulnerable pattern: sprintf with user-controlled input and no bounds checking.
        {"id": 2001, "code": 'sprintf(buf, "%s", input);', "label": "VULNERABLE"},

        # Safer pattern: snprintf with explicit buffer size to avoid overflow.
        {"id": 2002, "code": 'snprintf(buf, sizeof(buf), "%s", input);', "label": "SAFE"},
    ]


def load_vul4j():
    """
    Return a tiny, hard-coded subset shaped like Vul4J samples (Java-style code).

    The examples reflect:
        - An out-of-bounds write on an array
        - A guarded write with a bounds check
    """
    return [
        # Vulnerable: writes to index 11 of an array of length 10 (out-of-bounds).
        {"id": 3001, "code": "byte[] b = new byte[10]; b[11]=1;", "label": "VULNERABLE"},

        # Safe: checks bounds before writing to the array.
        {"id": 3002, "code": "if (idx < arr.length) arr[idx]=1;", "label": "SAFE"},
    ]
