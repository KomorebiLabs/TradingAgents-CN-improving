from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Set
import json

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screener.config import SCREENER_UNIVERSE
from tradingagents.ui.screener_console import console

if TYPE_CHECKING:
    from tradingagents.screener.data_access import ScreenerDataAccess


@dataclass
class UniverseBuildResult:
    tickers: List[str]
    metadata: Dict[str, Any]


def guess_exchange_suffix(raw_code: str) -> str:
    code = (raw_code or "").strip()
    if code.startswith(("6", "9")):
        return "SH"
    if code.startswith(("0", "2", "3")):
        return "SZ"
    if code.startswith(("4", "8")):
        return "BJ"
    return ""


def format_ticker(raw_code: str) -> str:
    suffix = guess_exchange_suffix(raw_code)
    return f"{raw_code}.{suffix}" if suffix else raw_code


def get_screener_cache_dir(config: Dict[str, Any] | None = None) -> Path:
    config = config or DEFAULT_CONFIG
    configured_root = Path(config.get("data_cache_dir", DEFAULT_CONFIG["data_cache_dir"]))
    candidates = [
        configured_root / "screener",
        Path.cwd() / ".tradingagents" / "cache" / "screener",
    ]

    for screener_dir in candidates:
        try:
            screener_dir.mkdir(parents=True, exist_ok=True)
            return screener_dir
        except OSError:
            continue

    raise PermissionError("Unable to create a writable screener cache directory")


def load_universe_cache(cache_file: Path) -> UniverseBuildResult | None:
    if not cache_file.exists():
        return None

    payload = json.loads(cache_file.read_text(encoding="utf-8"))
    return UniverseBuildResult(
        tickers=list(payload.get("tickers", [])),
        metadata=dict(payload.get("metadata", {})),
    )


def save_universe_cache(cache_file: Path, result: UniverseBuildResult) -> None:
    payload = {
        "tickers": result.tickers,
        "metadata": result.metadata,
    }
    try:
        cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def _resolve_universe_profile(mode: str, config: Dict[str, Any]) -> str:
    universe_config = config.get("universe", {})
    mode_profile_map = universe_config.get("mode_profile_map", {})
    configured_profile = universe_config.get("profile")
    return mode_profile_map.get(mode, configured_profile or mode)


def _get_universe_definition(profile: str) -> Dict[str, Any]:
    if profile in SCREENER_UNIVERSE:
        return dict(SCREENER_UNIVERSE[profile])
    if profile.upper() in SCREENER_UNIVERSE:
        return dict(SCREENER_UNIVERSE[profile.upper()])
    return {
        "profile": profile,
        "source": "index_universe_baseline",
        "index_codes": list(SCREENER_UNIVERSE["MVP"]["index_codes"]),
        "expansion_mode": "index_union",
        "cache_key": f"{profile.lower()}_constituents",  # P-5.3 fix: unified cache key
        "source_signature": f"fallback:{profile.lower()}",
        "constituent_expansion_ready": False,
    }


def _fetch_constituents_for_indexes(
    index_codes: List[str],
    data_access: "ScreenerDataAccess | None" = None,
) -> List[str]:
    """从指数代码列表获取真实成分股代码列表（去重后）。

    使用 ScreenerDataAccess.fetch_index_constituents() 获取每个指数的成分股权重数据，
    提取'成分券代码'字段并合并去重。

    Args:
        index_codes: 指数代码列表，如 ["000300", "000905"]
        data_access: 可选，已初始化的 ScreenerDataAccess 实例。
                     如果不传，函数内部延迟创建。

    Returns:
        成分股代码列表（6位数字格式，如 ["600519", "000858", ...]）
        如果全部失败，返回空列表
    """
    console.print(f"[cyan]>> Fetching {len(index_codes)} index constituents...[/cyan]", end="\r")

    all_constituents: Set[str] = set()
    _da = data_access

    def _get_da():
        nonlocal _da
        if _da is None:
            from tradingagents.screener.data_access import ScreenerDataAccess
            _da = ScreenerDataAccess()
        return _da

    for i, idx_code in enumerate(index_codes):
        df = None
        try:
            da = _get_da()
            df = da.fetch_index_constituents(idx_code)
        except Exception:
            pass

        if df is None or getattr(df, "empty", True):
            continue

        # 提取成分股代码列（akshare 返回的列名可能有差异，尝试常见列名）
        code_col = None
        for col in ["成分券代码", "code", "成分股代码"]:
            if col in df.columns:
                code_col = col
                break

        if code_col is None:
            continue

        for raw_code in df[code_col].dropna().unique():
            code = str(raw_code).strip()
            if not code or code in ("", "nan", "None"):
                continue
            if code.isdigit() and len(code) >= 6:
                all_constituents.add(code)
            elif code.isdigit() and len(code) < 6:
                all_constituents.add(code.zfill(6))

    console.print()
    console.print(f"[green][OK] Index constituents fetched[/green]  [cyan]{len(all_constituents)}[/cyan] unique from [cyan]{len(index_codes)}[/cyan] indexes")
    return sorted(all_constituents)


def build_screening_universe(
    mode: str = "MVP",
    config: Dict[str, Any] | None = None,
    data_access: "ScreenerDataAccess | None" = None,
) -> UniverseBuildResult:
    """构建筛选股票池。

    Phase 2 修复（H1）：不再返回指数代码本身，而是通过 fetch_index_constituents()
    获取真实成分股代码列表。

    Args:
        mode: 运行模式，"MVP" / "EXTENDED" / "EXPERIMENTAL" / "FULL" / "FOCUSED" / "CUSTOM"
        config: 可选配置字典
        data_access: 可选，预创建的 ScreenerDataAccess 实例（用于获取真实成分股）

    Returns:
        UniverseBuildResult，包含真实股票代码列表和元信息
    """
    config = config or DEFAULT_CONFIG
    profile = _resolve_universe_profile(mode, config)
    universe_config = config.get("universe", {})
    custom_tickers = universe_config.get("custom_tickers", [])

    cache_dir = get_screener_cache_dir(config)

    if profile == "CUSTOM" and custom_tickers:
        console.print(f"[cyan]>> CUSTOM mode[/cyan]  [dim]loading {len(custom_tickers)} custom tickers[/dim]")
        normalized = _normalize_tickers(custom_tickers)
        formatted = [format_ticker(code) for code in normalized]
        result = UniverseBuildResult(
            tickers=normalized,
            metadata={
                "mode": mode,
                "profile": "CUSTOM",
                "source": "custom_static_list",
                "construction_stage": "p5_custom_universe",
                "built_at": datetime.now().isoformat(),
                "display_tickers": formatted,
                "ticker_count": len(normalized),
                "input_size": len(normalized),
                "deduped_size": len(normalized),
                "selection_basis": "cli_custom_tickers",
                "constituent_expansion_ready": True,
                "universe_mode": "CUSTOM",
            },
        )
        return result

    # P5-2: Handle FOCUSED profile
    if profile == "FOCUSED":
        focus_type = universe_config.get("focus_type")
        focus_value = universe_config.get("focus_value")
        console.print(f"[cyan]>> FOCUSED mode[/cyan]  [dim]focus=[/dim][white]{focus_type}[/white][dim]=[/dim][white]{focus_value}[/white]")
        return _build_focused_universe(
            mode=mode,
            focus_type=focus_type,
            focus_value=focus_value,
            config=config,
            data_access=data_access,
        )

    # Standard profiles (MVP / EXTENDED / EXPERIMENTAL / FULL): fetch index constituents
    universe_def = _get_universe_definition(profile)
    cache_key = f"{profile.lower()}_constituents"
    cache_file = cache_dir / f"universe_{cache_key}.json"
    cached = load_universe_cache(cache_file)
    if cached is not None:
        console.print(f"[green][OK] Universe ready (cached)[/green]  [cyan]{len(cached.tickers)}[/cyan] tickers  [dim]profile={profile}[/dim]")
        return cached

    console.print(f"[cyan]>> Building universe from index constituents...[/cyan]  [dim]profile={profile}[/dim]", end="\r")

    index_codes = list(universe_def.get("index_codes", []))
    constituents = _fetch_constituents_for_indexes(index_codes, data_access)


    if not constituents:
        raise RuntimeError(
            f"[Screener] All index constituent APIs failed for indexes {index_codes}. "
            f"Cannot build universe from ETF codes. "
            f"Check AkShare connectivity or try CUSTOM mode with explicit tickers."
        )

    formatted = [format_ticker(code) for code in constituents]
    result = UniverseBuildResult(
        tickers=list(constituents),
        metadata={
            "mode": mode,
            "profile": profile,
            "source": "index_constituent_expansion",
            "construction_stage": "p5_index_universe",
            "built_at": datetime.now().isoformat(),
            "index_codes_used": index_codes,
            "display_tickers": formatted,
            "ticker_count": len(constituents),
            "input_size": len(constituents),
            "deduped_size": len(constituents),
            "selection_basis": "csindex_constituent_expansion",
            "expansion_mode": universe_def.get("expansion_mode", "index_union"),
            "cache_key": cache_key,
            "source_signature": universe_def.get(
                "source_signature", f"csindex:{','.join(index_codes)}"
            ),
            "constituent_expansion_ready": True,
            "universe_mode": mode,
        },
    )
    save_universe_cache(cache_file, result)
    console.print(f"[green][OK] Universe ready[/green]  [cyan]{len(result.tickers)}[/cyan] stocks  [dim]cached to {cache_file.name}[/dim]")
    return result


def _normalize_tickers(tickers: List[str]) -> List[str]:
    """Normalize ticker list to 6-digit codes with deduplication."""
    normalized = []
    for code in tickers:
        code = str(code).strip()
        if code.isdigit() and len(code) < 6:
            code = code.zfill(6)
        if code.isdigit():
            normalized.append(code)
    return list(dict.fromkeys(normalized))  # deduplicate, preserve order


def _build_focused_universe(
    mode: str,
    focus_type: str | None,
    focus_value: str | None,
    config: Dict[str, Any],
    data_access: "ScreenerDataAccess | None" = None,
) -> UniverseBuildResult:
    """Build universe for FOCUSED mode.

    P5-2: Supports sector, theme, index, and file-based focus.
    """
    cache_dir = get_screener_cache_dir(config)

    # Default focus configuration
    focus_type = focus_type or "index"
    focus_value = focus_value or "000300"

    constituents: List[str] = []
    source_info = ""
    cache_key = f"focused_{focus_type}_{focus_value.lower()}"

    if focus_type == "index":
        # Focus by index constituents
        cache_file = cache_dir / f"universe_{cache_key}.json"
        cached = load_universe_cache(cache_file)
        if cached is not None:
            return cached

        constituents = _fetch_constituents_for_indexes([focus_value], data_access)
        source_info = f"index:{focus_value}"

    elif focus_type == "file":
        # Focus by file
        file_path = Path(focus_value)
        if file_path.exists():
            raw = file_path.read_text(encoding="utf-8").splitlines()
            constituents = _normalize_tickers(raw)
            source_info = f"file:{file_path.name}"
        else:
            constituents = []
            source_info = f"file:{focus_value} (not found)"

    elif focus_type in ("sector", "theme"):
        # Focus by sector/theme - P5-2: exact match -> alias map -> fail
        cache_file = cache_dir / f"universe_{cache_key}.json"
        cached = load_universe_cache(cache_file)
        if cached is not None:
            return cached

        # P5-2: Use strict resolution with explicit failure
        resolved_name, resolution_method = _resolve_sector_theme_name(focus_value, data_access)

        if resolved_name is None:
            # P5-2: Explicit failure - do NOT silent fallback to full market
            raise ValueError(
                f"[Screener] FOCUSED mode failed: sector/theme '{focus_value}' not found. "
                f"Resolution method: {resolution_method}. "
                f"Available aliases: {list(_SECTOR_ALIAS_MAP.keys())[:10]}... "
                f"Please use an exact concept name or a known alias."
            )

        constituents = _fetch_concept_constituents(resolved_name, data_access)
        source_info = f"{focus_type}:{focus_value} -> {resolved_name} ({resolution_method})"

    else:
        constituents = []
        source_info = f"unknown:{focus_type}"

    # Apply input size protection (deduplicate + stable sort)
    stagea_max = config.get("stagea_max_input", 500)
    if len(constituents) > stagea_max:
        # Stable sort and truncate
        constituents = list(dict.fromkeys(constituents))[:stagea_max]

    formatted = [format_ticker(code) for code in constituents]
    result = UniverseBuildResult(
        tickers=constituents,
        metadata={
            "mode": mode,
            "profile": "FOCUSED",
            "source": source_info,
            "construction_stage": "p5_focused_universe",
            "built_at": datetime.now().isoformat(),
            "display_tickers": formatted,
            "ticker_count": len(constituents),
            "input_size": len(constituents),
            "deduped_size": len(constituents),
            "selection_basis": f"focused_{focus_type}",
            "focus_type": focus_type,
            "focus_value": focus_value,
            "constituent_expansion_ready": False,
            "universe_mode": "FOCUSED",
            "cache_key": cache_key,
        },
    )

    # Save cache for index/file based focus
    if focus_type in ("index", "file"):
        cache_file = cache_dir / f"universe_{cache_key}.json"
        save_universe_cache(cache_file, result)

    return result


def _fetch_concept_constituents(
    concept_name: str,
    data_access: "ScreenerDataAccess | None" = None,
) -> List[str]:
    """Fetch stock constituents for a sector/theme concept."""
    _da = data_access

    def _get_da():
        nonlocal _da
        if _da is None:
            from tradingagents.screener.data_access import ScreenerDataAccess
            _da = ScreenerDataAccess()
        return _da

    try:
        da = _get_da()
        # Fetch concept constituents
        df = da.fetch_concept_constituents(concept_name)
        if df is None or getattr(df, "empty", True):
            return []

        # Extract stock codes from the DataFrame
        constituents: Set[str] = set()
        for col in ["code", "成分股代码", "stock_code"]:
            if col in df.columns:
                for raw_code in df[col].dropna().unique():
                    code = str(raw_code).strip()
                    if code.isdigit() and len(code) >= 6:
                        constituents.add(code)
                    elif code.isdigit():
                        constituents.add(code.zfill(6))
                break

        return sorted(constituents)
    except Exception:
        return []


# P5-2: Sector/Theme alias mapping
# exact match -> alias map -> fail resolution rule
_SECTOR_ALIAS_MAP: Dict[str, str] = {
    # Chinese semiconductor aliases
    "半导体": "半导体",
    "semiconductor": "半导体",
    "chip": "半导体",
    "芯片": "半导体",
    "集成电路": "半导体",
    # AI / artificial intelligence
    "ai": "人工智能",
    "人工智能": "人工智能",
    "artificial_intelligence": "人工智能",
    "机器学习": "人工智能",
    # New energy / EV
    "新能源": "新能源",
    "新能源汽车": "新能源汽车",
    "ev": "新能源汽车",
    "电动车": "新能源汽车",
    "锂电池": "锂电池",
    "lithium": "锂电池",
    # Healthcare / pharma
    "医疗": "医疗器械",
    "医药": "医药制造",
    "生物医药": "生物医药",
    "biotech": "生物医药",
    # Tech
    "云计算": "云计算",
    "cloud": "云计算",
    "大数据": "大数据",
    "bigdata": "大数据",
    "5g": "5G",
    "物联网": "物联网",
    "iot": "物联网",
}


def _resolve_sector_theme_name(raw_name: str, data_access: "ScreenerDataAccess | None" = None) -> tuple[str | None, str]:
    """Resolve sector/theme name using exact match -> alias map -> fail rule.

    P5-2: Returns (resolved_name, resolution_method).
    - resolved_name: The canonical name if found, None if failed
    - resolution_method: 'exact' | 'alias' | 'failed'
    """
    _da = data_access

    def _get_da():
        nonlocal _da
        if _da is None:
            from tradingagents.screener.data_access import ScreenerDataAccess
            _da = ScreenerDataAccess()
        return _da

    # Step 1: Exact match - check if the name exists directly in concept boards
    da = _get_da()
    try:
        # Try to fetch concept constituents directly with the name
        result = da.fetch_concept_constituents(raw_name)
        if result is not None and not getattr(result, "empty", True):
            return raw_name, "exact"
    except Exception:
        pass

    # Step 2: Alias map lookup
    alias_name = _SECTOR_ALIAS_MAP.get(raw_name.lower())
    if alias_name:
        try:
            result = da.fetch_concept_constituents(alias_name)
            if result is not None and not getattr(result, "empty", True):
                return alias_name, "alias"
        except Exception:
            pass

    # Step 3: Explicit failure - do NOT fallback silently
    return None, "failed"
