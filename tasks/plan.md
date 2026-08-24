# Implementation Plan: Official Announcements, Independent Financial Data, and Unified Vendor Health

## Overview

Add a reliable-source path for Chinese listed-company announcements and independent financial statements, then expose one health model across the main dataflow router and the existing screener data access layer.

## Architecture Decisions

- Use official disclosure endpoints as a separate announcement source; do not treat scraped media news as equivalent to regulatory announcements.
- Add an optional token-backed independent financial adapter. Missing credentials must produce an explicit `not_configured` health state and preserve the existing fallback chain.
- Put the shared health tracker under `tradingagents.dataflows` so the low-level dataflow layer does not depend on the screener layer.
- Record outcome categories (`ok`, `empty`, `rate_limited`, `schema_error`, `auth_error`, `timeout`, `exception`, `not_configured`) rather than only a boolean failure count.
- Store only aggregate health data in run artifacts; never write API keys or raw authorization headers.

## Task List

### Phase 1: Research and contract

- [x] Confirm official announcement request/response constraints and independent financial API configuration.
- [x] Define normalized announcement and financial statement output contracts.
- [x] Define vendor health states and route-level aggregation.

### Phase 2: Foundation

- [x] Add shared `VendorHealthTracker` and compatibility exports for the existing screener tracker.
- [x] Add tests for every health outcome and redaction behavior.

### Phase 3: Source adapters

- [x] Add official announcement adapter with date, ticker, title, source URL, and disclosure type.
- [x] Add independent financial adapter with report period, publication date, units, and provenance.
- [x] Register both adapters with explicit fallback behavior and live probes.

### Phase 4: Integration

- [x] Instrument `route_to_vendor` with the shared tracker and explicit source health snapshots.
- [x] Add health summary to run artifacts and degraded messages.
- [x] Add route tests proving official-source and independent-financial fallback behavior.

### Checkpoint: Complete

- [x] Full offline tests pass.
- [x] Compile and diff checks pass.
- [x] Live read-only probes show source response or an explicit non-healthy state.
- [x] No secret appears in logs or artifacts.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Official endpoint changes or anti-bot controls | High | Keep adapter isolated, classify schema/HTTP failures, retain fallback sources |
| Financial API needs a token | Medium | Optional configuration and `not_configured` state; no hard startup failure |
| Shared tracker changes existing screener behavior | Medium | Compatibility re-export and existing health tests |
| PIT leakage from current snapshots | High | Require report period/publication date fields before evidence verification |
