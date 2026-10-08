# Task Plan: Reading 随机七套问答检查

## Goal
从已缓存且 A/B/C 三节均有可用答案的卷子中，固定随机种子抽七套；每套问一道，覆盖三种题型，走真实问答入口并对照缓存 KEYS。

## Next Step
七次真实问答和异常复核完毕；交付结果。

## Current Phase
Phase 5

## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify constraints
- [x] Document in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] Define approach
- [x] Reuse existing Service and evaluation helpers
- **Status:** complete

### Phase 3: Implementation
- [x] Execute seven independent Service calls
- [x] Record sampling before executing
- **Status:** complete

### Phase 4: Testing & Verification
- [x] Verify KEYS and output structure
- [x] Document the Section B Q42 source-evidence defect
- **Status:** complete

### Phase 5: Delivery
- [x] Review outputs
- [x] Deliver to user
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|

## Errors Encountered
| Error | Resolution |
|-------|------------|
