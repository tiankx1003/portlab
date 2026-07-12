"""标的代码工具函数。"""


def strip_market_prefix(symbol: str) -> str:
    """去除市场前缀（SH/SZ/BJ，大小写不敏感），返回纯代码。

    例：``SZ000001`` / ``sz000001`` / ``000001`` → ``000001``
    """
    s = symbol.strip().upper()
    for pfx in ("SH", "SZ", "BJ"):
        if s.startswith(pfx):
            return s[len(pfx):].strip()
    return s
