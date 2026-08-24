"""B5: A-share microstructure execution constraints for the decision layer.

Trader / Portfolio-Manager prompts MUST carry these hard rules so plans are
executable on the A-share market (T+1, price limits, friction costs) instead
of theoretical paper trades. Breakeven anchoring rule included: without a
defined anchor price, an LLM will happily compute breakeven off an
optimistic intraday low.

Rules are constants with a user-override file (~/.tradingagents/exchange_rules.json)
so a fee change never requires a code change.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

DEFAULT_RULES: Dict[str, float] = {
    "commission_rate": 0.00025,   # 佣金 万2.5（双边收取）
    "stamp_duty_sell": 0.0005,    # 印花税（仅卖出）
    "slippage": 0.001,            # 滑点假设（单边）
    "main_board_limit": 0.10,     # 主板涨跌停 ±10%
    "chinext_star_limit": 0.20,   # 创业板/科创板 ±20%
}


def load_rules() -> Dict[str, float]:
    """Defaults merged with the user override file (best-effort)."""
    rules = dict(DEFAULT_RULES)
    config_dir = Path.home() / ".tradingagents"
    override = config_dir / "exchange_rules.yaml"
    if not override.is_file():
        override = config_dir / "exchange_rules.json"
    try:
        if override.is_file():
            if override.suffix.lower() in {".yaml", ".yml"}:
                user = yaml.safe_load(override.read_text(encoding="utf-8")) or {}
            else:
                user = json.loads(override.read_text(encoding="utf-8"))
            for k, v in user.items():
                if k in rules and isinstance(v, (int, float)):
                    rules[k] = float(v)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        logger.warning("[exchange_rules] override file unreadable, using defaults: %s", exc)
    return rules


def round_trip_friction(rules: Dict[str, float]) -> float:
    """Approximate round-trip friction as a fraction of entry price."""
    return 2 * rules["commission_rate"] + rules["stamp_duty_sell"] + 2 * rules["slippage"]


_PRICE_RE = re.compile(
    r"((?:挂单价|执行价|限价|建议价|price)\s*[:：]?\s*)(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def validate_execution_decision(
    decision: str,
    *,
    trade_date_close: float | None,
    segment: str = "",
    trade_date: str = "",
) -> tuple[str, list[dict]]:
    """Validate explicit execution claims without guessing missing prices."""
    rules = load_rules()
    corrected = str(decision)
    warnings: list[dict] = []
    low = corrected.lower()
    is_sell = bool(re.search(r"\b(?:sell|卖出|减仓|止损)\b", low, re.IGNORECASE))
    if is_sell and not any(token in corrected for token in ("T+1", "次日", "不可当日")):
        warnings.append({"code": "t_plus_one", "message": "卖出语义缺少 T+1 次日执行说明"})
        corrected += "（次日开盘触发，遵守 T+1）"

    if trade_date_close is None or trade_date_close <= 0:
        if "盈亏平衡" in corrected:
            warnings.append({"code": "missing_anchor", "message": "缺少分析日收盘价锚定"})
        return corrected, warnings

    limit = rules["chinext_star_limit"] if segment in ("chinext", "star") else rules["main_board_limit"]
    lower = trade_date_close * (1 - limit)
    upper = trade_date_close * (1 + limit)
    for match in list(_PRICE_RE.finditer(corrected)):
        proposed = float(match.group(2))
        bounded = min(upper, max(lower, proposed))
        if bounded != proposed:
            warnings.append({
                "code": "price_limit",
                "message": f"价格 {proposed:g} 超出涨跌停区间，已限制到 {bounded:g}",
                "proposed": proposed,
                "corrected": bounded,
            })
            corrected = corrected[:match.start(2)] + f"{bounded:g}" + corrected[match.end(2):]
        if abs(proposed - trade_date_close) / trade_date_close > 0.02:
            warnings.append({
                "code": "anchor_deviation",
                "message": f"自报价格偏离分析日收盘价超过 2%（锚定价 {trade_date_close:g}）",
                "proposed": proposed,
                "anchor": trade_date_close,
            })

    if "盈亏平衡" in corrected and "收盘价" not in corrected:
        warnings.append({
            "code": "breakeven_anchor",
            "message": "盈亏平衡没有声明使用分析日收盘价作为锚定价",
        })
    return corrected, warnings


def execution_constraint_block(ticker: str, segment: str = "") -> str:
    """The prompt block every decision-producing agent must carry (B5)."""
    rules = load_rules()
    limit = rules["chinext_star_limit"] if segment in ("chinext", "star") else rules["main_board_limit"]
    friction_pct = round_trip_friction(rules) * 100
    return f"""
【A股执行硬约束（必须遵守，违反即计划无效）】
- T+1：当日买入不可当日卖出——止损与减仓动作一律表述为"次日开盘触发"，禁止暗示当日回转。
- 涨跌停：本标的适用 ±{limit:.0%}（{"创业板/科创板" if segment in ("chinext", "star") else "主板"}）；涨停价附近不追买（买不到），跌停无法卖出（流动性风险必须提示）。
- 摩擦成本：佣金 {rules['commission_rate']:.4%}（双边）+ 印花税 {rules['stamp_duty_sell']:.4%}（卖出）+ 滑点 {rules['slippage']:.1%}（假设，单边）≈ 往返合计约 {friction_pct:.2f}%。
- 【盈亏平衡锚定价规则】盈亏平衡计算一律以分析日收盘价为唯一锚定价；自报限价仅为执行建议，且偏离锚定价 >2% 时必须显式说明理由。
- <decision> 必须包含一行"盈亏平衡：需上涨 X%（基于收盘价锚定，含摩擦成本）"。
"""


def portfolio_prompt_block(portfolio: Dict[str, Any], ticker: str) -> str:
    """B3: portfolio context block; empty string when no portfolio file."""
    if not portfolio:
        return ""
    holdings = portfolio.get("holdings") or []
    constraints = portfolio.get("constraints") or {}
    lines = ["【组合上下文（仓位建议必须在此框架内给出）】"]
    if holdings:
        held = [h for h in holdings if str(h.get("ticker", "")).strip().upper() == str(ticker).strip().upper()]
        lines.append("当前持仓：" + (f"{ticker} 占比 {held[0].get('weight'):.0%}" if held else f"不含 {ticker}"))
        other = "; ".join(f"{h.get('ticker')} {float(h.get('weight', 0)):.0%}" for h in holdings[:6])
        lines.append(f"其他持仓：{other}")
    if constraints.get("max_single") is not None:
        lines.append(f"硬约束：单票上限 {float(constraints['max_single']):.0%}（系统层有程序化钳制，超限会被强制修正并留痕）")
    if constraints.get("max_industry") is not None:
        lines.append(f"硬约束：同行业上限 {float(constraints['max_industry']):.0%}")
    if constraints.get("cash_ratio") is not None:
        lines.append(f"现金比例要求：{float(constraints['cash_ratio']):.0%}")
    lines.append("仓位建议必须引用上述约束；已达上限时给出维持/减持建议而非加仓。")
    return "\n".join(lines) + "\n"
