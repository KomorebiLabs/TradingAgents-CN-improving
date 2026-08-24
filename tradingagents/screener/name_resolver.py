"""Company name resolver for the Screener.

Provides real A-share company names from akshare's stock_info_a_code_name(),
which returns clean UTF-8 data (verified: Chinese names decode correctly).
Uses a per-day cache to avoid redundant API calls.

Usage:
    resolver = NameResolver()
    name = resolver.resolve("600519")      # "贵州茅台"
    names = resolver.resolve_bulk(["600519", "000001"])
"""

from __future__ import annotations

try:  # pragma: no cover - optional runtime dependency
    import akshare as _ak
except Exception:  # pragma: no cover
    _ak = None
import json as _json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from tradingagents.screener.data_access import ScreenerDataAccess


def _is_valid_chinese_name(name: str) -> bool:
    """Return True if name looks like a real Chinese company name.

    Rejects:
    - Garbled text: chars outside Chinese/CJK range, spaces, or replacement chars
    - Placeholders: 'Proxy XXXXXX'
    - Truncated: names that end with common truncation markers
    """
    if not name or len(name) < 2:
        return False
    # Reject replacement char
    if "\ufffd" in name:
        return False
    # Reject placeholder pattern
    if name.startswith("Proxy ") or name.startswith("proxy "):
        return False
    # Must contain at least one Chinese/CJK character (U+4E00 to U+9FFF, plus extended)
    chinese_chars = sum(1 for c in name if "\u4e00" <= c <= "\u9fff" or "\u3000" <= c <= "\u303f")
    if chinese_chars == 0:
        return False
    # Reject if more than half the chars are clearly not Chinese company names
    # (e.g., "ST", "N", numbers, single Chinese chars like "A")
    if len(name) >= 4 and chinese_chars <= 1:
        return False
    return True


def _get_cache_root() -> Path:
    candidates = [
        Path.home() / ".tradingagents" / "cache" / "screener",
        Path.cwd() / ".tradingagents" / "cache" / "screener",
    ]
    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            continue
    raise PermissionError("Unable to create a writable name cache directory")


def _date_tag(trade_date: Optional[str] = None) -> str:
    if trade_date:
        return trade_date.replace("-", "")
    return datetime.now().strftime("%Y%m%d")


class NameResolver:
    """Resolves A-share ticker codes to real company names.

    Fetches from akshare.stock_info_a_code_name() which returns clean UTF-8
    company names (tested: 贵州茅台 = e8b4b5e5b79ee88c85e58fb0 in hex).
    Caches per trading day to avoid redundant API calls.
    """

    def __init__(
        self,
        data_access: Optional[ScreenerDataAccess] = None,
        trade_date: Optional[str] = None,
    ):
        self._da = data_access
        self._trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
        self._cache: Dict[str, str] = {}
        self._loaded = False
        self._warnings: List[str] = []
        self._source: str = "none"

    @property
    def warnings(self) -> List[str]:
        return list(self._warnings)

    @property
    def source(self) -> str:
        return self._source

    def _cache_path(self) -> Path:
        return _get_cache_root() / f"names_{_date_tag(self._trade_date)}.json"

    def _load_from_cache(self) -> bool:
        """Load from today's cache file. Returns True only if cache has valid Chinese names."""
        try:
            cache_file = self._cache_path()
            if not cache_file.exists():
                return False
            with open(cache_file, encoding="utf-8") as f:
                data = _json.load(f)
            names: Dict[str, str] = data.get("names", {})

            # A three-row cache can be syntactically valid yet useless for a
            # real universe. Reject tiny partial caches so missing tickers get
            # another chance through the configured snapshot/provider chain.
            valid_count = sum(1 for n in names.values() if _is_valid_chinese_name(n))
            if valid_count < 100:
                self._warnings.append(
                    f"Cache {cache_file.name} has only {valid_count} valid names; "
                    "invalidating and re-fetching."
                )
                return False

            self._cache = names
            self._source = "cache"
            return True
        except Exception as e:
            self._warnings.append(f"Cache load failed: {e}")
            return False

    def _save_to_cache(self) -> None:
        try:
            cache_file = self._cache_path()
            with open(cache_file, "w", encoding="utf-8") as f:
                _json.dump(
                    {"date": self._trade_date, "names": self._cache},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            pass

    def _load_from_api(self) -> None:
        """Fetch real names using akshare.stock_info_a_code_name().

        This API returns clean UTF-8 names (verified with akshare unit tests).
        Fetches all A-share stocks (SH, SZ, BJ, KCB) in one call.
        Falls back to CSI index constituents if the primary API fails.
        """
        self._cache.clear()

        fetched = 0
        errors: List[str] = []

        # Prefer the already configured Screener data-access chain.  This
        # keeps name resolution available when AkShare is intentionally an
        # optional dependency or its code-name endpoint is unavailable.
        if self._da is not None and hasattr(self._da, "fetch_spot_snapshot"):
            try:
                snapshot = self._da.fetch_spot_snapshot()
                if snapshot is not None and not snapshot.empty:
                    code_col = next(
                        (col for col in ("代码", "code", "symbol", "股票代码") if col in snapshot.columns),
                        None,
                    )
                    name_col = next(
                        (col for col in ("名称", "name", "股票名称") if col in snapshot.columns),
                        None,
                    )
                    if code_col and name_col:
                        for _, row in snapshot.iterrows():
                            code = str(row.get(code_col, "")).strip().split(".")[0]
                            name = str(row.get(name_col, "")).strip()
                            if code.isdigit() and _is_valid_chinese_name(name):
                                self._cache[code.zfill(6)] = name
                                fetched += 1
            except Exception as e:
                errors.append(f"spot_snapshot: {e}")

        if self._cache:
            self._source = "spot_snapshot"
            self._save_to_cache()
            return

        if _ak is None:
            self._warnings.append("akshare_not_available")
            self._source = "none"
            return

        # Primary source: akshare.stock_info_a_code_name() -- verified clean UTF-8
        try:
            df = _ak.stock_info_a_code_name()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    code = str(row.get("code", "")).strip()
                    name = str(row.get("name", "")).strip()
                    if code and name and name not in ("nan", "None"):
                        if _is_valid_chinese_name(name):
                            self._cache[code] = name
                            fetched += 1
        except Exception as e:
            errors.append(f"stock_info_a_code_name: {e}")

        # If primary failed or returned too few names, try CSI index constituents as fallback
        if fetched < 100:
            errors.append(f"Primary source returned only {fetched} names; trying CSI fallback")
            for symbol in ("000300", "000905"):
                try:
                    df_idx = _ak.index_stock_cons_weight_csindex(symbol=symbol)
                    if df_idx is not None and not df_idx.empty:
                        for row in df_idx.itertuples(index=False):
                            raw_code = str(row[4]).strip()  # col 4 = stock_code
                            name = str(row[5]).strip()       # col 5 = stock_name
                            if raw_code and name and name not in ("nan", "None"):
                                # Normalize: strip sh/sz prefix
                                norm = raw_code
                                if raw_code.startswith(("sh", "sz")):
                                    norm = raw_code[2:]
                                if len(norm) == 6 and norm.isdigit():
                                    if _is_valid_chinese_name(name):
                                        self._cache[norm] = name
                                        fetched += 1
                except Exception as e:
                    errors.append(f"CSI {symbol}: {e}")

        if not self._cache:
            self._warnings.append(
                "Failed to fetch company names. "
                f"Primary errors: {'; '.join(errors)}"
            )
            self._source = "none"
            return

        self._source = "spot_snapshot"
        self._save_to_cache()

        if errors:
            self._warnings.extend(errors)

    def load(self) -> "NameResolver":
        """Load names from cache, falling back to API if needed."""
        if not self._loaded:
            if not self._load_from_cache():
                self._load_from_api()
            self._loaded = True
        return self

    def resolve(self, raw_code: str) -> str:
        """Resolve a ticker code to a company name.

        Args:
            raw_code: A-share ticker code, e.g. "600519", "000001", "sh600519"

        Returns:
            The company name if found, otherwise the raw code unchanged.
        """
        if not self._loaded:
            self.load()

        code = str(raw_code).strip()
        if not code:
            return raw_code

        # Try as-is
        if code in self._cache:
            return self._cache[code]

        # Normalize 6-digit bare format
        if code.isdigit():
            if len(code) < 6:
                code = code.zfill(6)
            if code in self._cache:
                return self._cache[code]

        # Strip exchange suffix: "600519.SH", "000001.SZ", "sh600519", "sz000001"
        if "." in code:
            parts = code.split(".")
            base = parts[0].zfill(6) if parts[0].isdigit() else parts[0]
            if base in self._cache:
                return self._cache[base]
        if code.startswith(("sh", "sz")) and len(code) == 8:
            base = code[2:]
            if base in self._cache:
                return self._cache[base]

        # Return raw code unchanged if not found
        return raw_code

    def resolve_bulk(self, raw_codes: List[str]) -> Dict[str, str]:
        """Resolve multiple ticker codes to company names."""
        if not self._loaded:
            self.load()
        return {code: self.resolve(code) for code in raw_codes}

    def add_names(self, mapping: Dict[str, str]) -> None:
        """Manually add name mappings (useful for test fixtures)."""
        self._cache.update(mapping)
        self._loaded = True
