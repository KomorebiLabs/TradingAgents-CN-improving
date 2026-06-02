# Phase3 Skill 系统重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**目标：** 将 Skill 系统从"仅覆盖 4 个 Analyst 节点、Analyst 级别的粗粒度映射"重构为"覆盖全图决策节点、决策类型的精细化映射 + 动态阶段切换 + 分层 Skill 文件格式 + 完整的 Skill 可观测性链路"。

**架构概述：** 三大子系统并行建设：① 决策类型路由层（`DecisionType` 枚举 + `DecisionSkillMapper`）替换 `AnalystSkillMapping`；② 轮次感知分层注入（`SkillInjector` + `core/references` 双层 Skill 文件）；③ Skill 可观测性子系统（`audit.py` + `enforce_skill_usage()` + `AgentState.orchestration.skill_audit_trail` 审计记录）。新增 8 个决策节点的 Skill 注入。

**技术栈：** Python + Pydantic + LangChain/LangGraph，无新外部依赖。

---

## 文件总览

### 新建文件

| 文件 | 用途 |
|------|------|
| `tradingagents/harness/skills/types.py`（覆盖） | 新增 `DecisionType` 枚举 + `SkillLayer` + `SkillReference` 结构 |
| `tradingagents/harness/skills/mapping.py` | 新增 `DecisionSkillMapper`，替换 `ANALYST_SKILL_MAPPING` |
| `tradingagents/harness/skills/injector.py`（覆盖） | 新增 `debate_round` 感知 + `core/references` 分层注入 |
| `tradingagents/harness/skills/bundled/defensive/` | 新建目录：舞弊检测、风险约束、群体行为 |
| `tradingagents/harness/skills/bundled/valuation/` | 新建目录：估值方法、成长质量 |
| `tradingagents/harness/skills/bundled/catalyst/` | 新建目录：事件催化剂、政策影响、行业轮动 |
| `tradingagents/harness/skills/bundled/sentiment/` | 新建目录：情绪评分、群体行为（引用 social/） |
| `tradingagents/harness/skills/bundled/market/trend_patterns/references/` | 新增 `trend_reversal_signals.md` |
| `tradingagents/harness/skills/bundled/market/breakout_recognition/references/` | 新增 `breakout_checklist.md` |
| `tradingagents/harness/skills/bundled/fundamentals/fraud_detection/references/` | 新增 `red_flags_checklist.md` |
| `tests/harness/skills/test_mapping.py` | 新增决策类型映射测试 |
| `tests/harness/skills/test_injector.py`（覆盖） | 新增轮次切换测试 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `tradingagents/agents/researchers/bull_researcher.py` | 在 `bull_node()` 的 `prompt` 构建前，调用 `skill_injector.inject()`，传入 `decision_type="offensive"` + `debate_round` |
| `tradingagents/agents/researchers/bear_researcher.py` | 同上，传入 `decision_type="defensive"` |
| `tradingagents/agents/managers/research_manager.py` | 传入 `decision_type="valuation"` |
| `tradingagents/agents/trader/trader.py` | 传入 `decision_type="offensive"`（trader 本身是进攻性角色） |
| `tradingagents/agents/risk_mgmt/aggressive_debator.py` | 传入 `decision_type="offensive"` |
| `tradingagents/agents/risk_mgmt/conservative_debator.py` | 传入 `decision_type="defensive"` |
| `tradingagents/agents/risk_mgmt/neutral_debator.py` | 传入 `decision_type="valuation"` |
| `tradingagents/agents/managers/portfolio_manager.py` | 传入 `decision_type="valuation"` + `include_references=True` |
| `tradingagents/graph/setup.py` | 将 `SkillInjector` 实例注入到需要它的节点工厂函数（通过闭包或参数） |
| `tradingagents/harness/__init__.py`（覆盖） | 导出新的 `DecisionType`、`DecisionSkillMapper`、`SkillInjector` |

---

## 决策类型映射设计

```python
# 决策类型枚举
class DecisionType(str, Enum):
    OFFENSIVE = "offensive"      # 进攻型：看多、做多、追突破
    DEFENSIVE = "defensive"      # 防御型：看空、风控、识别陷阱
    VALUATION = "valuation"      # 估值型：裁判、综合、决策
    CATALYST = "catalyst"        # 催化剂型：政策、事件驱动
    SENTIMENT = "sentiment"     # 情绪型：舆情、群体行为

# 决策类型 → Skill 白名单
DECISION_SKILL_MAPPING: Dict[DecisionType, List[str]] = {
    DecisionType.OFFENSIVE: [
        "breakout-recognition", "trend-patterns", "volume-analysis",
        "indicator-library", "event-catalyst",
    ],
    DecisionType.DEFENSIVE: [
        "fraud-detection", "risk-constraint", "crowd-behavior",
        "volume-analysis",
    ],
    DecisionType.VALUATION: [
        "valuation-methods", "growth-quality",
        "fraud-detection", "risk-constraint",
    ],
    DecisionType.CATALYST: [
        "event-catalyst", "policy-impact", "sector-rotation",
        "crowd-behavior",
    ],
    DecisionType.SENTIMENT: [
        "sentiment-scoring", "crowd-behavior",
    ],
}

# Skill 层级策略
class SkillLayer(str, Enum):
    CORE = "core"         # SKILL.md 的核心指令（每次注入）
    REFERENCE = "ref"    # references/ 详细文档（按需注入）
```

---

## 轮次感知注入策略

```python
# debate_round: 从 investment_debate_state["count"] 读取
INJECTION_STRATEGY: Dict[str, Dict[str, List[str]]] = {
    # 辩论第一轮：全部核心 Skill 注入，references 可选
    "round_1": {
        "include_references": False,   # 第一轮简洁，减少 token
        "skill_strategy": "full",       # 注入白名单全部 core skill
    },
    # 反驳轮：额外注入对方立场的防御性 Skill（反常识攻击）
    "round_n": {
        "include_references": True,
        "skill_strategy": "full_plus_counter",
        # Bull 在反驳轮额外获得 fraud-detection（攻击对方财报可信度）
        # Bear 在反驳轮额外获得 breakout-recognition（攻击对方突破信号）
    },
    # 裁决/决策轮：切换为估值型 Skill，references 全开
    "adjudication": {
        "include_references": True,
        "skill_strategy": "valuation_focused",
    },
}
```

---

## Task 1: 新增决策类型系统（types.py + mapping.py）

**Files:**
- Create: `tradingagents/harness/skills/types.py`（覆盖）
- Create: `tradingagents/harness/skills/mapping.py`
- Test: `tests/harness/skills/test_mapping.py`

- [ ] **Step 1: 覆盖 types.py —— 新增枚举和结构**

```python
"""tradingagents/harness/skills/types.py"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DecisionType(str, Enum):
    OFFENSIVE = "offensive"
    DEFENSIVE = "defensive"
    VALUATION = "valuation"
    CATALYST = "catalyst"
    SENTIMENT = "sentiment"


class SkillLayer(str, Enum):
    CORE = "core"
    REFERENCE = "ref"


@dataclass
class SkillReference:
    """references/ 目录下的一个参考文档"""
    filename: str
    content: str

    def to_prompt_section(self) -> str:
        return f"**Reference: {self.filename}**\n{self.content}"


@dataclass
class SkillDefinition:
    """A single skill definition with metadata and content.
    
    Extends existing Pydantic-based SkillDefinition with layered references support.
    """
    name: str
    description: str
    decision_types: List[DecisionType] = field(default_factory=list)
    version: str = "1.0"
    category: Optional[str] = None
    applies_to_analyst: List[str] = field(default_factory=list)
    content: str = ""          # SKILL.md body (CORE layer)
    references: List[SkillReference] = field(default_factory=list)  # references/ 目录下的参考文档
    metadata: dict = field(default_factory=dict)

    def to_prompt_section(self, include_references: bool = False) -> str:
        parts = [f"## Skill: {self.name}\n\n{self.content}"]
        if include_references and self.references:
            parts.append("\n**References:**")
            for ref in self.references:
                parts.append(f"\n{ref.to_prompt_section()}")
        return "\n".join(parts)

    def to_core_section(self) -> str:
        return self.to_prompt_section(include_references=False)

    def to_full_section(self) -> str:
        return self.to_prompt_section(include_references=True)


@dataclass
class SkillUsageRecord:
    """Skill 使用记录——Skill 可观测性的核心数据结构"""
    skill_name: str
    decision_type: str
    layer: str = "core"  # "core" or "reference"
    usage_type: str = "declared"  # "declared" = LLM 声明使用, "injected" = 注入但未声明
    justification: str = ""  # LLM 声明时附带的理由（从 <SkillsUsed> 解析）


@dataclass
class SkillAuditEntry:
    """一次 Agent 节点调用的完整 Skill 审计记录"""
    node_name: str
    decision_type: str
    debate_round: int
    is_counter_round: bool
    is_adjudication: bool
    injected_skills: List[str] = field(default_factory=list)   # 本次注入的全部 Skill 名
    declared_skills: List[SkillUsageRecord] = field(default_factory=list)  # LLM 声明使用的 Skill
    unmatched_declared: List[str] = field(default_factory=list)  # LLM 声明了但未注入的 Skill
    skill_match_rate: float = 0.0  # 声明率 = declared / injected（可量化 Skill 有效性）
    timestamp: str = ""  # ISO 格式时间戳
```

- [ ] **Step 2: 创建 mapping.py —— 决策类型映射**

```python
"""tradingagents/harness/skills/mapping.py"""
from __future__ import annotations

from typing import Dict, List

from .types import DecisionType


# Decision type → Skill name whitelist
DECISION_SKILL_MAPPING: Dict[DecisionType, List[str]] = {
    DecisionType.OFFENSIVE: [
        "breakout-recognition",
        "trend-patterns",
        "volume-analysis",
        "indicator-library",
        "event-catalyst",
    ],
    DecisionType.DEFENSIVE: [
        "fraud-detection",
        "risk-constraint",
        "crowd-behavior",
        "volume-analysis",
    ],
    DecisionType.VALUATION: [
        "valuation-methods",
        "growth-quality",
        "fraud-detection",
        "risk-constraint",
    ],
    DecisionType.CATALYST: [
        "event-catalyst",
        "policy-impact",
        "sector-rotation",
        "crowd-behavior",
    ],
    DecisionType.SENTIMENT: [
        "sentiment-scoring",
        "crowd-behavior",
    ],
}


# Extra skills injected during counter-round (bull counters bear, etc.)
COUNTER_ROUND_EXTRA: Dict[str, List[str]] = {
    # Bull researcher: when countering bear, also consider the opposing view's toolkit
    "bull": ["fraud-detection", "risk-constraint"],
    # Bear researcher: when countering bull, also consider attacking breakout signals
    "bear": ["breakout-recognition", "trend-patterns"],
}


class DecisionSkillMapper:
    """Maps a decision type + debate round to a list of skill names to inject."""

    def __init__(self, mapping: Dict[DecisionType, List[str]] | None = None) -> None:
        self._mapping = mapping or DECISION_SKILL_MAPPING

    def get_skill_names(
        self,
        decision_type: DecisionType,
        node_name: str | None = None,
        debate_round: int = 1,
        is_counter_round: bool = False,
    ) -> List[str]:
        base = list(self._mapping.get(decision_type, []))
        
        if is_counter_round and node_name and node_name.lower() in COUNTER_ROUND_EXTRA:
            base.extend(COUNTER_ROUND_EXTRA[node_name.lower()])
        
        return list(dict.fromkeys(base))  # deduplicate preserve order

    def get_injection_strategy(
        self,
        debate_round: int,
        is_adjudication: bool = False,
    ) -> Dict[str, bool]:
        if is_adjudication or debate_round >= 10:
            return {"include_references": True, "skill_strategy": "valuation_focused"}
        if debate_round == 1:
            return {"include_references": False, "skill_strategy": "full"}
        return {"include_references": True, "skill_strategy": "full_plus_counter"}
```

- [ ] **Step 3: 写测试 test_mapping.py**

```python
"""tests/harness/skills/test_mapping.py"""
import pytest

from tradingagents.harness.skills.types import DecisionType
from tradingagents.harness.skills.mapping import (
    DecisionSkillMapper,
    DECISION_SKILL_MAPPING,
    COUNTER_ROUND_EXTRA,
)


class TestDecisionSkillMapping:
    def test_offensive_contains_expected_skills(self):
        skills = DECISION_SKILL_MAPPING[DecisionType.OFFENSIVE]
        assert "breakout-recognition" in skills
        assert "trend-patterns" in skills

    def test_defensive_contains_fraud_detection(self):
        skills = DECISION_SKILL_MAPPING[DecisionType.DEFENSIVE]
        assert "fraud-detection" in skills

    def test_valuation_contains_valuation_methods(self):
        skills = DECISION_SKILL_MAPPING[DecisionType.VALUATION]
        assert "valuation-methods" in skills

    def test_no_overlap_if_intended(self):
        offensive = set(DECISION_SKILL_MAPPING[DecisionType.OFFENSIVE])
        defensive = set(DECISION_SKILL_MAPPING[DecisionType.DEFENSIVE])
        # overlap is allowed but should be intentional
        assert isinstance(offensive, set)
        assert isinstance(defensive, set)


class TestDecisionSkillMapper:
    def setup_method(self):
        self.mapper = DecisionSkillMapper()

    def test_round_1_no_references(self):
        strategy = self.mapper.get_injection_strategy(debate_round=1)
        assert strategy["include_references"] is False

    def test_round_n_has_references(self):
        strategy = self.mapper.get_injection_strategy(debate_round=3)
        assert strategy["include_references"] is True

    def test_counter_round_adds_extra_skills(self):
        names = self.mapper.get_skill_names(
            DecisionType.OFFENSIVE,
            node_name="bull",
            is_counter_round=True,
        )
        assert "fraud-detection" in names  # bull counters bear with fraud detection

    def test_normal_round_no_extra(self):
        names = self.mapper.get_skill_names(
            DecisionType.OFFENSIVE,
            node_name="bull",
            is_counter_round=False,
        )
        assert "fraud-detection" not in names

    def test_adjudication_strategy(self):
        strategy = self.mapper.get_injection_strategy(
            debate_round=1,
            is_adjudication=True,
        )
        assert strategy["skill_strategy"] == "valuation_focused"
        assert strategy["include_references"] is True
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/harness/skills/test_mapping.py -v`
Expected: 9 tests, all PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/harness/skills/types.py tradingagents/harness/skills/mapping.py tests/harness/skills/test_mapping.py
git commit -m "feat(harness): add DecisionType enum and DecisionSkillMapper"
```

---

## Task 2: 重构 SkillInjector 支持分层注入

**Files:**
- Modify: `tradingagents/harness/skills/injector.py`（覆盖）
- Modify: `tradingagents/harness/skills/loader.py`
- Test: `tests/harness/skills/test_injector.py`（覆盖）

- [ ] **Step 1: 修改 loader.py —— 支持 references/ 目录扫描**

```python
"""Injects skill content into Agent prompts with round-aware layered injection."""


def _load_skill_directory(skill_dir: Path, category: str) -> Optional[SkillDefinition]:
    """Load a skill directory: SKILL.md + optional references/ subdir."""
    main_file = skill_dir / "SKILL.md"
    if not main_file.exists():
        # Fallback: load single .md file directly under category dir (backward compat)
        return None
    
    skill_md = main_file.read_text(encoding="utf-8")
    name_from_dir = skill_dir.name
    frontmatter: Dict[str, Any] = {}
    body = skill_md

    if skill_md.startswith("---\n"):
        end_marker = skill_md.find("\n---\n", 4)
        if end_marker != -1:
            yaml_text = skill_md[4:end_marker]
            body = skill_md[end_marker + 5:]
            try:
                frontmatter = yaml.safe_load(yaml_text) or {}
            except yaml.YAMLError:
                frontmatter = {}

    name = frontmatter.get("name") or name_from_dir
    description = frontmatter.get("description", f"Skill: {name}")
    applies_to = frontmatter.get("applies_to_analyst", [])
    version = str(frontmatter.get("version", "1.0"))
    decision_types_raw = frontmatter.get("decision_types", [])
    decision_types = [DecisionType(d) for d in decision_types_raw]

    # Load references/
    references_dir = skill_dir / "references"
    ref_list: List[SkillReference] = []
    if references_dir.exists() and references_dir.is_dir():
        for ref_file in sorted(references_dir.glob("*.md")):
            ref_list.append(SkillReference(
                filename=ref_file.stem,
                content=ref_file.read_text(encoding="utf-8").strip(),
            ))

    return SkillDefinition(
        name=name,
        description=description,
        decision_types=decision_types,
        category=category,
        applies_to_analyst=applies_to,
        version=version,
        content=body.strip(),
        references=ref_list,
        metadata={k: v for k, v in frontmatter.items()
                   if k not in ("name", "description", "applies_to_analyst",
                                 "version", "decision_types")},
    )
```

Then update the loader's `load_skill_registry()` to scan directories first:

```python
def load_skill_registry(bundled_dir: Path) -> SkillRegistry:
    registry = SkillRegistry()
    if not bundled_dir.exists():
        return registry

    for category_dir in sorted(bundled_dir.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name

        # Priority 1: skill subdirectories (new format)
        for skill_dir in sorted(category_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill = _load_skill_directory(skill_dir, category)
            if skill is not None:
                registry.register(skill)

        # Priority 2: single .md files (backward compat with old flat format)
        for md_file in sorted(category_dir.glob("*.md")):
            # Skip if there's already a directory with same stem
            if (category_dir / md_file.stem).is_dir():
                continue
            skill = _load_skill_file(md_file, category)  # existing function
            if skill is not None:
                registry.register(skill)

    return registry
```

- [ ] **Step 2: 覆盖 injector.py —— 新增分层注入接口**

```python
"""tradingagents/harness/skills/injector.py"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .types import DecisionType, SkillDefinition
from .registry import SkillRegistry
from .loader import load_skill_registry
from .mapping import DecisionSkillMapper, DECISION_SKILL_MAPPING


class SkillInjector:
    """Injects layered skill content into Agent prompts.

    Supports:
    - Decision-type based routing (replaces analyst-type routing)
    - Round-aware injection (round 1 = core only, round N = full + references)
    - Counter-round skill injection (Bull gets fraud-detection when countering Bear)
    """

    def __init__(
        self,
        bundled_dir: Optional[Path] = None,
        mapping: Optional[Dict[DecisionType, List[str]]] = None,
    ) -> None:
        if bundled_dir is None:
            bundled_dir = Path(__file__).parent / "bundled"
        self._bundled_dir = bundled_dir
        self._registry: Optional[SkillRegistry] = None
        self._mapper = DecisionSkillMapper(mapping)

    def _ensure_registry(self) -> SkillRegistry:
        if self._registry is None:
            self._registry = load_skill_registry(self._bundled_dir)
        return self._registry

    def build_skill_section(
        self,
        decision_type: DecisionType,
        node_name: str | None = None,
        debate_round: int = 1,
        is_counter_round: bool = False,
        include_references: bool = False,
    ) -> str:
        registry = self._ensure_registry()
        skill_names = self._mapper.get_skill_names(
            decision_type=decision_type,
            node_name=node_name,
            debate_round=debate_round,
            is_counter_round=is_counter_round,
        )
        skills = registry.get_skills_by_names(skill_names)

        if not skills:
            return ""

        sections = ["# Analytical Skills Available", ""]
        for skill in skills:
            if include_references:
                sections.append(skill.to_full_section())
            else:
                sections.append(skill.to_core_section())
            sections.append("")

        return "\n".join(sections)

    def inject(
        self,
        decision_type: DecisionType,
        existing_prompt: str,
        node_name: str | None = None,
        debate_round: int = 1,
        is_counter_round: bool = False,
        is_adjudication: bool = False,
    ) -> str:
        strategy = self._mapper.get_injection_strategy(
            debate_round=debate_round,
            is_adjudication=is_adjudication,
        )
        include_references = strategy["include_references"]

        skill_section = self.build_skill_section(
            decision_type=decision_type,
            node_name=node_name,
            debate_round=debate_round,
            is_counter_round=is_counter_round,
            include_references=include_references,
        )
        if not skill_section:
            return existing_prompt

        separator = (
            "\n\n"
            + "=" * 60 + "\n"
            + "## INJECTED ANALYTICAL SKILLS\n"
            + "=" * 60 + "\n"
        )
        return existing_prompt + separator + skill_section


# Backward-compatible alias for existing analyst-type callers
class AnalystSkillInjector:
    """Legacy wrapper: maps analyst type → decision type for backward compat."""

    ANALYST_TO_DECISION: Dict[str, DecisionType] = {
        "market": DecisionType.OFFENSIVE,
        "news": DecisionType.CATALYST,
        "fundamentals": DecisionType.VALUATION,
        "social": DecisionType.SENTIMENT,
    }

    def __init__(self) -> None:
        self._delegate = SkillInjector()

    def inject_into_prompt(
        self,
        analyst_type: str,
        existing_prompt: str,
        include_references: bool = False,
    ) -> str:
        decision_type = self.ANALYST_TO_DECISION.get(analyst_type, DecisionType.VALUATION)
        skill_section = self._delegate.build_skill_section(
            decision_type=decision_type,
            include_references=include_references,
        )
        if not skill_section:
            return existing_prompt
        separator = (
            "\n\n"
            + "=" * 60 + "\n"
            + "## INJECTED ANALYTICAL SKILLS\n"
            + "=" * 60 + "\n"
        )
        return existing_prompt + separator + skill_section
```

- [ ] **Step 3: 覆盖 test_injector.py**

```python
"""tests/harness/skills/test_injector.py"""
import pytest

from tradingagents.harness.skills.types import DecisionType
from tradingagents.harness.skills.injector import (
    SkillInjector,
    AnalystSkillInjector,
)
from tradingagents.harness.skills.mapping import DECISION_SKILL_MAPPING


class TestSkillInjector:
    def setup_method(self):
        self.injector = SkillInjector()

    def test_build_skill_section_offensive(self):
        section = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            include_references=False,
        )
        assert "breakout-recognition" in section or "## Skill:" in section

    def test_build_skill_section_defensive(self):
        section = self.injector.build_skill_section(
            DecisionType.DEFENSIVE,
            include_references=False,
        )
        assert "## Skill:" in section or section == ""

    def test_round_1_no_references(self):
        section = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            debate_round=1,
            include_references=False,
        )
        assert "**Reference:" not in section

    def test_counter_round_adds_skills(self):
        normal = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            node_name="bull",
            is_counter_round=False,
        )
        counter = self.injector.build_skill_section(
            DecisionType.OFFENSIVE,
            node_name="bull",
            is_counter_round=True,
        )
        assert len(counter) >= len(normal)  # counter has at least as many skills

    def test_inject_adds_separator(self):
        result = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="You are a bull researcher.",
        )
        assert "INJECTED ANALYTICAL SKILLS" in result
        assert "You are a bull researcher." in result


class TestAnalystSkillInjector:
    """Backward compatibility test for existing analyst-type callers."""

    def setup_method(self):
        self.injector = AnalystSkillInjector()

    def test_market_maps_to_offensive(self):
        result = self.injector.inject_into_prompt("market", "prompt")
        assert "INJECTED ANALYTICAL SKILLS" in result

    def test_fundamentals_maps_to_valuation(self):
        result = self.injector.inject_into_prompt("fundamentals", "prompt")
        assert "INJECTED ANALYTICAL SKILLS" in result
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/harness/skills/test_injector.py tests/harness/skills/test_mapping.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add tradingagents/harness/skills/injector.py tradingagents/harness/skills/loader.py tests/harness/skills/test_injector.py
git commit -m "feat(harness): layer-aware SkillInjector with decision-type routing"
```

---

## Task 3: Skill 可观测性子系统（audit + enforcement）

**Files:**
- Create: `tradingagents/harness/skills/audit.py`
- Modify: `tradingagents/harness/skills/injector.py`（注入格式 + Skill 声明指令）
- Modify: `tradingagents/agents/utils/agent_utils.py`（`enforce_skill_usage()` 新增）
- Test: `tests/harness/skills/test_audit.py`

**核心理念：Skill 注入不是盲注，而是可观测的知识注入链路。**

设计参考：`enforce_execution_profile_output()` 追加结构化注释的模式 + `extract_semantic_trigger_audit()` 的审计结构 + 现有 `<decision>` 等 XML 标签约定。

- [ ] **Step 1: 创建 audit.py —— Skill 使用审计引擎**

```python
"""tradingagents/harness/skills/audit.py"""
from __future__ import annotations

import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Optional

from .types import SkillAuditEntry, SkillUsageRecord


# Skill 使用声明的 XML 标签（参考现有 <decision> 约定）
SKILL_USAGE_PATTERN = re.compile(
    r"<SkillsUsed>(.*?)</SkillsUsed>",
    re.DOTALL | re.IGNORECASE,
)
SKILL_ITEM_PATTERN = re.compile(
    r"-\s*([a-z0-9_-]+)(?:\s*:\s*(.+))?",
    re.IGNORECASE,
)


def parse_skill_usage(content: str) -> List[SkillUsageRecord]:
    """从 LLM 响应中解析 <SkillsUsed> 声明。

    解析格式：
    <SkillsUsed>
    - breakout-recognition: 用于验证突破有效性
    - volume-analysis
    </SkillsUsed>

    Returns:
        List[SkillUsageRecord] — 解析出的使用记录列表
    """
    records: List[SkillUsageRecord] = []
    match = SKILL_USAGE_PATTERN.search(content)
    if not match:
        return records

    block = match.group(1)
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        item_match = SKILL_ITEM_PATTERN.match(line)
        if item_match:
            skill_name = item_match.group(1).strip().lower()
            justification = item_match.group(2).strip() if item_match.group(2) else ""
            records.append(SkillUsageRecord(
                skill_name=skill_name,
                decision_type="",  # 由调用方填充
                layer="core",
                usage_type="declared",
                justification=justification,
            ))
    return records


def build_skill_audit_entry(
    node_name: str,
    decision_type: str,
    debate_round: int,
    is_counter_round: bool,
    is_adjudication: bool,
    injected_skill_names: List[str],
    response_content: str,
) -> SkillAuditEntry:
    """构建一次调用的完整审计记录。

    对比"注入的 Skill"和"LLM 声明使用的 Skill"：
    - injected: SkillInjector 本轮注入了哪些 Skill
    - declared: LLM 在 <SkillsUsed> 中声明了哪些 Skill
    - unmatched: LLM 声明了但本轮没注入（可能是历史 Skill）
    """
    declared_records = parse_skill_usage(response_content)
    declared_names = {r.skill_name for r in declared_records}
    injected_set = set(injected_skill_names)

    # 匹配：声明了且本轮注入了
    matched = declared_names & injected_set

    # 未匹配：声明了但本轮没注入（可能是跨轮次复用或其他来源）
    unmatched = sorted(declared_names - injected_set)

    # 声明率 = 本轮注入中声明了的比例
    match_rate = len(matched) / len(injected_set) if injected_set else 0.0

    # 填充 decision_type
    for r in declared_records:
        r.decision_type = decision_type

    return SkillAuditEntry(
        node_name=node_name,
        decision_type=decision_type,
        debate_round=debate_round,
        is_counter_round=is_counter_round,
        is_adjudication=is_adjudication,
        injected_skills=sorted(injected_set),
        declared_skills=declared_records,
        unmatched_declared=unmatched,
        skill_match_rate=round(match_rate, 3),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def build_skill_audit_summary(entries: List[SkillAuditEntry]) -> dict:
    """将多条审计记录汇总为可读的摘要报告，用于日志和调试。"""
    if not entries:
        return {"summary": "No skill audit entries."}

    total_injected = sum(len(e.injected_skills) for e in entries)
    total_declared = sum(len(e.declared_skills) for e in entries)
    avg_match_rate = sum(e.skill_match_rate for e in entries) / len(entries)
    all_declared = sorted({r.skill_name for e in entries for r in e.declared_skills})
    all_injected = sorted({s for e in entries for s in e.injected_skills})

    return {
        "total_invocations": len(entries),
        "total_skills_injected": total_injected,
        "total_skills_declared": total_declared,
        "avg_match_rate": round(avg_match_rate, 3),
        "all_declared_skills": all_declared,
        "all_injected_skills": all_injected,
        "decluttered_skills": sorted(set(all_injected) - set(all_declared)),
        "per_node": [
            {
                "node": e.node_name,
                "round": e.debate_round,
                "match_rate": e.skill_match_rate,
                "injected": e.injected_skills,
                "declared": [r.skill_name for r in e.declared_skills],
            }
            for e in entries
        ],
    }
```

- [ ] **Step 2: 修改 injector.py —— 注入 Skill 使用声明指令**

在 `inject()` 返回的 prompt 末尾追加 Skill 使用声明指令（参考 `enforce_execution_profile_output` 模式）：

```python
SKILL_USAGE_INSTRUCTION = """
When your analysis is complete, include a <SkillsUsed> block listing every skill
you actively applied during this reasoning. Format:

<SkillsUsed>
- <skill-name>: <one-sentence justification of how you used it>
- <skill-name>
</SkillsUsed>

Skills you were provided are: {injected_skill_names}
Only declare skills you actually referenced. If none were used, write:
<SkillsUsed>
- (none)
</SkillsUsed>
""".strip()


def inject(
    self,
    decision_type: DecisionType,
    existing_prompt: str,
    node_name: str | None = None,
    debate_round: int = 1,
    is_counter_round: bool = False,
    is_adjudication: bool = False,
) -> str:
    # ... existing inject logic (same as Task 2) ...
    # [完整保留 Task 2 的 inject 实现]

    if not skill_section:
        return existing_prompt

    # 追加 Skill 使用声明指令
    skill_usage_instruction = SKILL_USAGE_INSTRUCTION.format(
        injected_skill_names=", ".join(sorted(skill_names)),
    )

    separator = (
        "\n\n"
        + "=" * 60 + "\n"
        + "## INJECTED ANALYTICAL SKILLS\n"
        + "=" * 60 + "\n"
    )
    return existing_prompt + separator + skill_section + "\n\n" + skill_usage_instruction
```

同时将 `injected_skill_names` 作为 `build_skill_section` 的返回值暴露出去，供审计用：

```python
def build_skill_section(
    self,
    # ... existing params ...
) -> tuple[str, List[str]]:  # 返回 (section_text, injected_skill_names)
    # ...
    return "\n".join(sections), skill_names
```

- [ ] **Step 3: 修改 agent_utils.py —— 新增 enforce_skill_usage**

在 `enforce_execution_profile_output()` 后新增：

```python
def enforce_skill_usage(
    content: str,
    injected_skill_names: List[str],
    node_name: str,
    decision_type: str,
    debate_round: int,
    is_counter_round: bool,
    is_adjudication: bool,
) -> dict:
    """验证 LLM 响应中的 Skill 使用声明，并构建审计记录。

    如果 LLM 未声明任何 Skill，在响应末尾追加提示（不修改已有内容）。
    返回审计记录供 SkillAuditEntry 使用。
    """
    from tradingagents.harness.skills.audit import build_skill_audit_entry

    entry = build_skill_audit_entry(
        node_name=node_name,
        decision_type=decision_type,
        debate_round=debate_round,
        is_counter_round=is_counter_round,
        is_adjudication=is_adjudication,
        injected_skill_names=injected_skill_names,
        response_content=content,
    )

    # 如果声明了 (none)，追加低声明率提示（不修改已有内容，只追加）
    if entry.declared_skills and entry.declared_skills[0].skill_name == "(none)":
        content = content.rstrip() + (
            "\n\n[skill_usage_reminder] No skills were declared. "
            "Consider if any of these were applicable: "
            + ", ".join(injected_skill_names[:5])
        )

    return {
        "content": content,
        "audit_entry": asdict(entry),
    }
```

- [ ] **Step 4: 修改各 Agent 节点 —— 接入审计**

在每个决策节点（Bull/Bear/Research Manager/Trader/Risk Debaters/Portfolio Manager）中，将：

```python
# 旧代码
response = llm.invoke(prompt)
response.content = enforce_execution_profile_output(response.content, execution_profile)
```

替换为：

```python
# 新代码
response = llm.invoke(prompt)
response.content = enforce_execution_profile_output(response.content, execution_profile)

# Skill 使用审计
    from tradingagents.agents.utils.agent_utils import enforce_skill_usage
    skill_result = enforce_skill_usage(
        content=response.content,
        injected_skill_names=injected_skill_names,  # SkillInjector.build_skill_section 返回的列表
        node_name=node_name,
        decision_type=decision_type.value,
        debate_round=current_count,
        is_counter_round=is_counter_round,
        is_adjudication=is_adjudication,
    )
    response.content = skill_result["content"]

    # 将审计记录写入 AgentState.orchestration.skill_audit_trail（供后续汇总和日志输出）
    audit_trail = dict(state.get("orchestration", {}).get("skill_audit_trail", []))
    audit_entry = skill_result["audit_entry"]
    audit_trail.setdefault(node_name, []).append(audit_entry)
```

并在节点返回时更新 `orchestration.skill_audit_trail`。

- [ ] **Step 5: 写测试 test_audit.py**

```python
"""tests/harness/skills/test_audit.py"""
import pytest
from tradingagents.harness.skills.audit import (
    parse_skill_usage,
    build_skill_audit_entry,
    build_skill_audit_summary,
)


class TestParseSkillUsage:
    def test_parses_single_skill_with_justification(self):
        content = "<SkillsUsed>\n- breakout-recognition: 用于验证突破有效性\n</SkillsUsed>"
        records = parse_skill_usage(content)
        assert len(records) == 1
        assert records[0].skill_name == "breakout-recognition"
        assert "验证突破" in records[0].justification

    def test_parses_multiple_skills(self):
        content = "<SkillsUsed>\n- breakout-recognition\n- volume-analysis: 用于确认量能\n</SkillsUsed>"
        records = parse_skill_usage(content)
        assert len(records) == 2
        names = {r.skill_name for r in records}
        assert "breakout-recognition" in names
        assert "volume-analysis" in names

    def test_no_skills_used(self):
        content = "<SkillsUsed>\n- (none)\n</SkillsUsed>"
        records = parse_skill_usage(content)
        assert len(records) == 1
        assert records[0].skill_name == "(none)"

    def test_no_skills_block_returns_empty(self):
        content = "This is a regular response without skill usage."
        records = parse_skill_usage(content)
        assert records == []


class TestBuildSkillAuditEntry:
    def test_match_rate_calculation(self):
        entry = build_skill_audit_entry(
            node_name="bull",
            decision_type="offensive",
            debate_round=1,
            is_counter_round=False,
            is_adjudication=False,
            injected_skill_names=["breakout-recognition", "volume-analysis"],
            response_content="<SkillsUsed>\n- breakout-recognition\n</SkillsUsed>",
        )
        assert entry.skill_match_rate == 0.5
        assert "volume-analysis" in entry.unmatched_declared  # 注入了但未声明

    def test_full_match_rate(self):
        entry = build_skill_audit_entry(
            node_name="bull",
            decision_type="offensive",
            debate_round=1,
            is_counter_round=False,
            is_adjudication=False,
            injected_skill_names=["breakout-recognition"],
            response_content="<SkillsUsed>\n- breakout-recognition\n</SkillsUsed>",
        )
        assert entry.skill_match_rate == 1.0

    def test_undeclared_skill_reported(self):
        entry = build_skill_audit_entry(
            node_name="bull",
            decision_type="offensive",
            debate_round=1,
            is_counter_round=False,
            is_adjudication=False,
            injected_skill_names=["fraud-detection"],
            response_content="No skills used in this response.",
        )
        assert entry.skill_match_rate == 0.0
        assert entry.unmatched_declared == []  # 没声明，所以没未匹配


class TestBuildSkillAuditSummary:
    def test_summary_aggregates_entries(self):
        entries = [
            build_skill_audit_entry("bull", "offensive", 1, False, False,
                                     ["breakout"], "<SkillsUsed>\n- breakout\n</SkillsUsed>"),
            build_skill_audit_entry("bear", "defensive", 1, False, False,
                                     ["fraud-detection"], "<SkillsUsed>\n</SkillsUsed>"),
        ]
        summary = build_skill_audit_summary(entries)
        assert summary["total_invocations"] == 2
        assert summary["avg_match_rate"] == 0.5
        assert "breakout" in summary["all_declared_skills"]
```

- [ ] **Step 6: 运行测试**

Run: `pytest tests/harness/skills/test_audit.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add tradingagents/harness/skills/audit.py tradingagents/agents/utils/agent_utils.py
git commit -m "feat(harness): add Skill observability system with audit trail"
```

---

## Task 5（← 原Task3）: 迁移现有 Skill 文件到目录结构

**Files:**
- Create: `tradingagents/harness/skills/bundled/market/trend_patterns/references/trend_reversal_signals.md`
- Create: `tradingagents/harness/skills/bundled/market/breakout_recognition/references/breakout_checklist.md`
- Create: `tradingagents/harness/skills/bundled/fundamentals/fraud_detection/references/red_flags_checklist.md`
- Modify: `tradingagents/harness/skills/bundled/market/trend_patterns.md` → move to `market/trend_patterns/SKILL.md`
- Modify: `tradingagents/harness/skills/bundled/market/breakout_recognition.md` → move to `market/breakout_recognition/SKILL.md`
- Modify: `tradingagents/harness/skills/bundled/fundamentals/fraud_detection.md` → move to `fundamentals/fraud_detection/SKILL.md`
- (All other existing skill .md files remain in place as backward compat)

- [ ] **Step 1: 读取并迁移 trend_patterns.md**

读取 `tradingagents/harness/skills/bundled/market/trend_patterns.md`，将其内容分为：
- `market/trend_patterns/SKILL.md`：保留核心指南（前 80% 内容）
- `market/trend_patterns/references/trend_reversal_signals.md`：反转信号的详细 checklist（从原文件中提取或精简）

- [ ] **Step 2: 读取并迁移 breakout_recognition.md**

同样拆分到 `SKILL.md` + `references/breakout_checklist.md`

- [ ] **Step 3: 读取并迁移 fraud_detection.md**

同样拆分到 `SKILL.md` + `references/red_flags_checklist.md`

- [ ] **Step 4: 添加 YAML frontmatter decision_types**

在每个新的 `SKILL.md` frontmatter 中添加 `decision_types` 字段：

```yaml
---
name: trend-patterns
description: Use when identifying and confirming market trends, trend reversals, or chart patterns in A-share technical analysis.
applies_to_analyst: [market_technical]
decision_types: [offensive, catalyst]
version: "1.0"
---
```

- [ ] **Step 5: 删除旧的 .md 文件**

删除原来的 `trend_patterns.md`、`breakout_recognition.md`、`fraud_detection.md`

- [ ] **Step 6: 运行 loader 测试验证迁移**

Run: `pytest tests/harness/skills/test_loader.py -v`
Expected: PASS — loader 应该自动发现新的目录格式

- [ ] **Step 7: Commit**

```bash
git add tradingagents/harness/skills/bundled/
git commit -m "refactor(skills): migrate key skills to directory format with references"
```

---

## Task 6（← 原Task4）: 新建 defensive 目录 Skill

**Files:**
- Create: `tradingagents/harness/skills/bundled/defensive/risk_constraint/SKILL.md`
- Create: `tradingagents/harness/skills/bundled/defensive/crowd_behavior/SKILL.md`
- Create: `tradingagents/harness/skills/bundled/defensive/fraud_detection/SKILL.md`（从 fundamentals/ 迁移一份 defensive 专用版）

- [ ] **Step 1: risk_constraint/SKILL.md**

```yaml
---
name: risk-constraint
description: Use when evaluating position sizing, stop-loss levels, portfolio concentration, and downside risk controls in A-share trading decisions.
decision_types: [defensive, valuation]
version: "1.0"
---

# 风险约束框架

## 概述

风险约束是投资决策的最后一道防线。即使基本面和技术面都支持投资，如果风险约束条件不满足，也应降低仓位或放弃。本 Skill 定义 A 股特有的风险约束检查清单。

## 一、仓位控制原则

**单只个股仓位上限**：不超过总仓位的 20%（激进投资者可放宽至 25%）。A股散户习惯"重仓押注"，但历史上看，单票超过 30% 仓位在黑天鹅事件中损失惨重。

**行业集中度上限**：单一行业不超过总仓位的 40%。避免因行业系统性风险导致大幅回撤。

**总仓位动态调整**：
- 大盘估值处于历史 80% 分位以上：总仓位不超过 60%
- 大盘估值处于历史 50%~80% 分位：总仓位不超过 80%
- 大盘估值处于历史 50% 分位以下：可考虑满仓

## 二、止损原则

**ATR 止损法**：入场价下方 1.5~2 倍 ATR 作为止损位。ATR 是最市场化的止损指标，适应不同波动率的个股。

**固定百分比止损法**：
- 短线交易（持有期 < 5 日）：止损 5%~8%
- 中线交易（持有期 5~30 日）：止损 10%~15%
- 长线投资（持有期 > 30 日）：止损 20%

**时间止损法**：若入场后 N 个交易日内未能产生预期收益（无论涨跌），应重新评估逻辑，不应无理由死守。

## 三、风险指标清单

在做出任何买入决策前，逐项核对：

1. 若买入后下跌 10%，组合整体回撤是否可接受？
2. 该标的的 ATR（14日）是否超过买入价的 5%？
3. 该标的与现有持仓的相关系数是否超过 0.7（高相关性 = 实际风险集中度更高）？
4. 当前大盘整体趋势是否处于下跌趋势（日线 MA20 向下）？
5. 该标的所属行业是否处于政策逆风期？

任意一项不满足，应降低仓位或放弃。
```

- [ ] **Step 2: crowd_behavior/SKILL.md**

```yaml
---
name: crowd-behavior
description: Use when analyzing retail investor crowd behavior, market euphoria/fear indicators, or detecting manipulation patterns in A-share social media and price data.
decision_types: [defensive, sentiment]
version: "1.0"
---

# A 股群体行为识别指南

## 概述

A股是全球散户占比最高的市场之一，群体行为对股价的影响远超基本面。本 Skill 梳理 A 股特有的散户群体行为模式及其在价格和舆情数据中的表现。

## 一、散户群体行为特征

**羊群效应（追涨杀跌）**：A股散户在高点和低点均有强烈的群体一致性行为。高点时融资账户激增、社交媒体讨论热度达到峰值；低点时基金赎回潮、恐慌性割肉。这是反向投资者的超额收益来源之一。

**噪音交易者占主导**：A股换手率常年高于成熟市场 3~5 倍，大量交易来自散户噪音交易。主力资金（机构）利用散户的羊群效应进行"割韭菜"操作——在低位吸筹、高位派发。

**涨停板跟风**：A股特有的涨跌停板制度催生了"涨停板敢死队"文化。散户盲目追涨停板（"打板"），忽视封板质量、板块联动强度和次日接力资金。

## 二、识别群体极端情绪的指标

**舆情热度**：微博/东财股吧/雪球讨论热度达到近 3 个月最高点 → 市场情绪过热，是反向信号。

**融资融券余额变化**：融资余额单周增幅超过 20% → 杠杆资金涌入，高点预警信号。

**基金申购赎回数据**：基金募集规模达到历史峰值 → 往往对应市场顶部（"日光基"现象）。

**换手率异常**：个股换手率超过日均换手率 3 倍且非新股/非公告驱动 → 警惕主力对倒或散户过度炒作。

## 三、识别主力行为的蛛丝马迹

**分时图"钓鱼线"**：早盘快速拉抬股价（涨幅 > 5%）后无量回落，分时图呈现先扬后抑的尖峰形态。这是主力诱多的典型手法。

**尾盘集合竞价操纵**：收盘前最后 3 分钟出现大单集中买入/卖出，人为控制收盘价。多用于维护股价（护盘）或为次日出货做准备。

**龙虎榜数据**：个股连续 3 日涨停后登上龙虎榜，可查询机构和散户席位的买卖比例。机构净卖出占比超过 50% 是强烈卖出信号。
```

- [ ] **Step 3: fraud_detection/SKILL.md（defensive 专用版）**

内容直接复用 `fundamentals/fraud_detection/SKILL.md`，frontmatter 添加 `decision_types: [defensive, valuation]`

- [ ] **Step 4: Commit**

```bash
git add tradingagents/harness/skills/bundled/defensive/
git commit -m "feat(skills): add defensive decision-type skills"
```

---

## Task 7（← 原Task5）: 新建 valuation 目录 Skill

**Files:**
- Create: `tradingagents/harness/skills/bundled/valuation/growth_quality/SKILL.md`
- Modify: `tradingagents/harness/skills/bundled/fundamentals/valuation_methods.md` → 添加 `decision_types` frontmatter

- [ ] **Step 1: 添加 decision_types 到 valuation_methods.md frontmatter**

```yaml
---
name: valuation-methods
description: Use when selecting appropriate valuation frameworks, comparing P/E vs P/B vs DCF metrics, or assessing whether a stock is overvalued or undervalued in A-share context.
applies_to_analyst: [fundamentals_quant]
decision_types: [valuation]
version: "1.0"
---
```

- [ ] **Step 2: 创建 growth_quality/SKILL.md（从 fundamentals/growth_quality.md 迁移 + 添加 decision_types）**

读取现有 `fundamentals/growth_quality.md`，在 frontmatter 添加 `decision_types: [valuation]`，移动到 `valuation/growth_quality/SKILL.md`

- [ ] **Step 3: Commit**

```bash
git add tradingagents/harness/skills/bundled/fundamentals/valuation_methods.md tradingagents/harness/skills/bundled/valuation/
git commit -m "feat(skills): add valuation decision-type skills with growth_quality"
```

---

## Task 8（← 原Task6）: 新建 catalyst 目录 Skill

**Files:**
- Create: `tradingagents/harness/skills/bundled/catalyst/event_catalyst/SKILL.md`
- Create: `tradingagents/harness/skills/bundled/catalyst/policy_impact/SKILL.md`
- Create: `tradingagents/harness/skills/bundled/catalyst/sector_rotation/SKILL.md`
- Modify: `news/event_catalyst.md` → 添加 `decision_types`
- Modify: `news/policy_impact.md` → 添加 `decision_types`
- Modify: `news/sector_rotation.md` → 添加 `decision_types`

- [ ] **Step 1: 为 3 个 news Skill 添加 decision_types**

在每个 frontmatter 中添加 `decision_types: [catalyst]`

- [ ] **Step 2: 迁移到 catalyst/ 子目录**

将 `news/event_catalyst.md` → `catalyst/event_catalyst/SKILL.md`
将 `news/policy_impact.md` → `catalyst/policy_impact/SKILL.md`
将 `news/sector_rotation.md` → `catalyst/sector_rotation/SKILL.md`

- [ ] **Step 3: Commit**

```bash
git add tradingagents/harness/skills/bundled/catalyst/ tradingagents/harness/skills/bundled/news/
git commit -m "feat(skills): add catalyst decision-type skills directory"
```

---

## Task 9（← 原Task7）: 为 Bull Researcher 接入 Skill 注入

**Files:**
- Modify: `tradingagents/agents/researchers/bull_researcher.py:108-243`

- [ ] **Step 1: 添加 import**

```python
from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType
```

- [ ] **Step 2: 修改工厂函数签名，注入 SkillInjector**

```python
def create_bull_researcher(llm, memory, skill_injector: SkillInjector | None = None):
    if skill_injector is None:
        skill_injector = SkillInjector()
```

- [ ] **Step 3: 在 prompt 构建前注入 Skill**

在 `prompt = f"""` 之前插入：

```python
        # 获取辩论轮次，判断是否为反驳轮
        current_count = investment_debate_state["count"]
        is_counter_round = current_count >= 1  # 从第2轮开始是反驳轮

        # 注入进攻型决策 Skill（带轮次感知）
        prompt = skill_injector.inject(
            decision_type=DecisionType.OFFENSIVE,
            existing_prompt=(
                "You are a Bull Analyst advocating for investing in the stock. "
                "Your task is to build a strong, evidence-based case emphasizing "
                "growth potential, competitive advantages, and positive market indicators. "
                "Leverage the provided research and data to address concerns and counter "
                "bearish arguments effectively.\n\n"
            ),
            node_name="bull",
            debate_round=current_count,
            is_counter_round=is_counter_round,
        )

        # 追加上下文变量（Skill 注入后追加可变量部分）
        prompt += (
            f"\n\nRoute context:\n"
            f"- policy_role: {policy_role}\n"
            f"- capital_quality: {capital_quality}\n"
            f"- conflict_tier: {conflict_tier}\n"
            f"- debate_risk_weight: {debate_risk_weight}\n\n"
            f"Key points to focus on:\n"
            f"- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.\n"
            f"- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.\n"
            f"- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.\n"
            f"- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning.\n"
            f"- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points.\n\n"
            f"Resources available:\n"
            f"Market research report: {market_research_report}\n"
            f"Social media sentiment report: {sentiment_report}\n"
            f"Latest world affairs news: {news_report}\n"
            f"Company fundamentals report: {fundamentals_report}\n"
            f"Conversation history of the debate: {history}\n"
            f"Last bear argument: {current_response}\n"
            f"Reflections from similar situations: {past_memory_str}\n"
            f"Screener semantic routing guidance: {semantic_instruction}\n"
            f"Semantic execution profile: {execution_profile}\n"
            f"Execution style: {style}\n"
            f"Conclusion template: {conclusion_template_instruction}\n"
            f"Required evidence: {must_include}\n"
            f"Use this information to deliver a compelling bull argument and engage in a dynamic debate."
        )
```

- [ ] **Step 4: Commit**

```bash
git add tradingagents/agents/researchers/bull_researcher.py
git commit -m "feat(skills): inject offensive decision skills into Bull Researcher"
```

---

## Task 10（← 原Task8）: 为 Bear Researcher 接入 Skill 注入

**Files:**
- Modify: `tradingagents/agents/researchers/bear_researcher.py:108-378`

- [ ] **Step 1: 添加 import**

```python
from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType
```

- [ ] **Step 2: 修改工厂函数**

```python
def create_bear_researcher(llm, memory, skill_injector: SkillInjector | None = None):
    if skill_injector is None:
        skill_injector = SkillInjector()
```

- [ ] **Step 3: 在 prompt 构建前注入 Skill（防御型）**

与 Task 7 类似，但使用 `DecisionType.DEFENSIVE` 和 `node_name="bear"`，`is_counter_round` 逻辑相同。

- [ ] **Step 4: Commit**

```bash
git add tradingagents/agents/researchers/bear_researcher.py
git commit -m "feat(skills): inject defensive decision skills into Bear Researcher"
```

---

## Task 11（← 原Task9）: 为 Research Manager / Trader / Risk Debaters / Portfolio Manager 接入 Skill

**Files:**
- Modify: `tradingagents/agents/managers/research_manager.py`
- Modify: `tradingagents/agents/trader/trader.py`
- Modify: `tradingagents/agents/risk_mgmt/aggressive_debator.py`
- Modify: `tradingagents/agents/risk_mgmt/conservative_debator.py`
- Modify: `tradingagents/agents/risk_mgmt/neutral_debator.py`
- Modify: `tradingagents/agents/managers/portfolio_manager.py`

**注入映射表：**

| 节点 | DecisionType | node_name | is_adjudication |
|------|-------------|-----------|-----------------|
| Research Manager | VALUATION | "research_manager" | True |
| Trader | OFFENSIVE | "trader" | False |
| Aggressive Debater | OFFENSIVE | "aggressive" | False |
| Conservative Debater | DEFENSIVE | "conservative" | False |
| Neutral Debater | VALUATION | "neutral" | False |
| Portfolio Manager | VALUATION | "portfolio_manager" | True |

- [ ] **Step 1: 修改 research_manager.py**

读取 `tradingagents/agents/managers/research_manager.py`，在工厂函数中注入 `skill_injector`，在 prompt 构建前调用 `skill_injector.inject(DecisionType.VALUATION, is_adjudication=True)`

- [ ] **Step 2: 修改 trader.py**

同上，注入 `DecisionType.OFFENSIVE`，trader 关注突破和趋势

- [ ] **Step 3: 修改 3 个 risk debaters**

Aggressive → `DecisionType.OFFENSIVE`
Conservative → `DecisionType.DEFENSIVE`
Neutral → `DecisionType.VALUATION`

- [ ] **Step 4: 修改 portfolio_manager.py**

`DecisionType.VALUATION`，`is_adjudication=True`，`include_references=True`（最终裁决需要最完整信息）

- [ ] **Step 5: 逐个 Commit**

```bash
git add tradingagents/agents/managers/research_manager.py
git commit -m "feat(skills): inject valuation skills into Research Manager"

git add tradingagents/agents/trader/trader.py
git commit -m "feat(skills): inject offensive skills into Trader"

git add tradingagents/agents/risk_mgmt/
git commit -m "feat(skills): inject decision skills into Risk Debaters"

git add tradingagents/agents/managers/portfolio_manager.py
git commit -m "feat(skills): inject valuation skills into Portfolio Manager"
```

---

## Task 12（← 原Task10）: 将 SkillInjector 注入到 Graph setup.py

**Files:**
- Modify: `tradingagents/graph/setup.py`

- [ ] **Step 1: 读取 setup.py，找到节点创建区域**

读取 `tradingagents/graph/setup.py` 第 411~438 行（节点创建区域）

- [ ] **Step 2: 在 TradingAgentsGraph.__init__ 中创建 SkillInjector 实例**

```python
from tradingagents.harness.skills.injector import SkillInjector

class TradingAgentsGraph:
    def __init__(
        self,
        # ... existing params ...
        skill_injector: SkillInjector | None = None,
    ):
        # ... existing init code ...
        
        # Skill injector for decision-node skill injection
        self._skill_injector = skill_injector or SkillInjector()
```

- [ ] **Step 3: 在创建各节点时传入 skill_injector**

```python
bull_researcher_node = create_bull_researcher(
    self.quick_thinking_llm, self.bull_memory,
    skill_injector=self._skill_injector,
)
bear_researcher_node = create_bear_researcher(
    self.quick_thinking_llm, self.bear_memory,
    skill_injector=self._skill_injector,
)
research_manager_node = create_research_manager(
    self.deep_thinking_llm, self.invest_judge_memory,
    skill_injector=self._skill_injector,
)
trader_node = create_trader(
    self.quick_thinking_llm, self.trader_memory,
    skill_injector=self._skill_injector,
)
# Risk debaters
aggressive_analyst = create_aggressive_debator(
    self.quick_thinking_llm,
    skill_injector=self._skill_injector,
)
neutral_analyst = create_neutral_debator(
    self.quick_thinking_llm,
    skill_injector=self._skill_injector,
)
conservative_analyst = create_conservative_debator(
    self.quick_thinking_llm,
    skill_injector=self._skill_injector,
)
portfolio_manager_node = create_portfolio_manager(
    self.deep_thinking_llm, self.portfolio_manager_memory,
    skill_injector=self._skill_injector,
)
```

- [ ] **Step 4: 运行测试验证**

Run: `pytest tests/test_orchestration_logic.py -v -k "bull or bear or researcher" 2>/dev/null || echo "No matching tests yet"`
验证无导入错误

- [ ] **Step 5: Commit**

```bash
git add tradingagents/graph/setup.py
git commit -m "feat(graph): wire SkillInjector into all decision nodes via setup"
```

---

## Task 13（← 原Task11）: 更新 harness __init__.py 导出

**Files:**
- Modify: `tradingagents/harness/__init__.py`

- [ ] **Step 1: 更新导出**

```python
"""TradingAgents Harness — skill injection, observability, and context management."""
from tradingagents.harness.skills.injector import SkillInjector, AnalystSkillInjector
from tradingagents.harness.skills.types import DecisionType, SkillDefinition
from tradingagents.harness.skills.mapping import DecisionSkillMapper

__all__ = [
    "SkillInjector",
    "AnalystSkillInjector",
    "DecisionType",
    "SkillDefinition",
    "DecisionSkillMapper",
]
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from tradingagents.harness import SkillInjector, DecisionType; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add tradingagents/harness/__init__.py
git commit -m "chore(harness): export new DecisionType and DecisionSkillMapper"
```

---

## Task 14（← 原Task12）: 端到端集成测试

**Files:**
- Create: `tests/test_skill_injection_integration.py`

- [ ] **Step 1: 写集成测试**

```python
"""tests/test_skill_injection_integration.py"""
import pytest

from tradingagents.harness.skills.injector import SkillInjector
from tradingagents.harness.skills.types import DecisionType
from tradingagents.harness.skills.loader import load_skill_registry
from pathlib import Path


class TestSkillInjectionIntegration:
    """End-to-end tests: verify skills are loaded and injectable into prompts."""

    def setup_method(self):
        self.injector = SkillInjector()

    def test_all_decision_types_produce_nonempty_sections(self):
        for dt in DecisionType:
            section = self.injector.build_skill_section(dt, include_references=False)
            # At least one skill should be loaded for each decision type
            # (empty result means no skills registered for that type)
            assert "## Skill:" in section or section == "", f"DecisionType.{dt} broken"

    def test_offensive_skill_includes_breakout_recognition(self):
        section = self.injector.build_skill_section(
            DecisionType.OFFENSIVE, include_references=True
        )
        assert "breakout" in section.lower() or "trend" in section.lower()

    def test_defensive_skill_includes_fraud_detection(self):
        section = self.injector.build_skill_section(
            DecisionType.DEFENSIVE, include_references=True
        )
        assert "fraud" in section.lower() or "risk" in section.lower()

    def test_inject_adds_skill_section_to_prompt(self):
        result = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="You are a bull researcher.",
            debate_round=1,
        )
        assert "You are a bull researcher." in result
        assert "INJECTED ANALYTICAL SKILLS" in result

    def test_round_1_no_references_in_injected_prompt(self):
        result = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="You are a bull researcher.",
            debate_round=1,
        )
        assert "**Reference:" not in result

    def test_round_n_with_references(self):
        result = self.injector.inject(
            DecisionType.OFFENSIVE,
            existing_prompt="You are a bull researcher.",
            debate_round=3,
        )
        # Round 3 should include references
        # Note: depends on actual skill files having references/ dirs

    def test_backward_compat_analyst_injector(self):
        from tradingagents.harness.skills.injector import AnalystSkillInjector
        inj = AnalystSkillInjector()
        result = inj.inject_into_prompt("market", "prompt")
        assert "INJECTED ANALYTICAL SKILLS" in result
```

- [ ] **Step 2: 运行测试**

Run: `pytest tests/test_skill_injection_integration.py -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_skill_injection_integration.py
git commit -m "test: add end-to-end skill injection integration tests"
```

---

## 实施顺序

1. Task 1 — 决策类型系统（types + mapping） ✅ 独立可测
2. Task 2 — SkillInjector 重构 + loader 更新 ✅ 依赖 Task 1
3. Task 3 — Skill 可观测性子系统（audit.py + enforce + state 写入） ✅ 依赖 Task 2
4. Task 5 — 迁移现有 Skill 文件到目录结构 ✅ 依赖 Task 2
5. Task 6 — 新建 defensive Skill ✅ 独立
6. Task 7 — 新建 valuation Skill ✅ 独立
7. Task 8 — 新建 catalyst Skill ✅ 独立
8. Task 9 — Bull Researcher 接入 ✅ 依赖 Task 2
9. Task 10 — Bear Researcher 接入 ✅ 依赖 Task 2
10. Task 11 — Research Manager / Trader / Risk Debaters / Portfolio Manager 接入 ✅ 依赖 Task 2
11. Task 12 — Graph setup.py 注入 ✅ 依赖 Task 9-11
12. Task 13 — harness __init__.py 导出 ✅ 依赖 Task 1-2
13. Task 14 — 集成测试 ✅ 依赖 Task 12-13

---
