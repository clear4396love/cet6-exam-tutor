# Task Plan: 六级翻译方法与缓存覆盖审计

## Goal
清理用户提供的教师方法中的误导性绝对规则，并对 38 篇缓存翻译原文做可追溯的试译与覆盖审计，交付规则、逐篇结果及未覆盖清单。

## Next Step
已完成方法卡与 38 篇试译审计；向用户交付文件及覆盖边界。

## Current Phase
Phase 1

## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify constraints
- [x] Document in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] Define approach and per-paper QA criteria
- [x] Prepare isolated audit artifacts
- **Status:** complete

### Phase 3: Implementation
- [x] Draft conditional method guide
- [x] Trial-translate the 38 cached passages
- [x] Record source-text uncertainty and recurring gaps
- **Status:** complete

### Phase 4: Testing & Verification
- [x] Verify paper count, source fidelity and output completeness
- [x] Spot-check risky grammar and terminology
- **Status:** complete

### Phase 5: Delivery
- [x] Review outputs
- [x] Deliver to user
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Keep formal parsed_papers untouched | OCR uncertainties must not silently rewrite the question bank. |
| Mark teacher notes, corrections and inferences separately | Avoid attributing revised advice to the lecturer. |
| Use two Markdown deliverables, no new app feature or dependency | Existing cache and direct translation suffice for a first coverage audit; ponytail keeps scope minimal. |
| Draft all 38 translations directly and label them trial answers | Local Python virtual environments are broken; new runtime/API integration is not justified for the language audit. |
| Preserve contested source facts in trial text with prominent warning and authoritative links | Separate translation fidelity from independent fact verification. |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| Initial completeness check used an overstrict English-token pattern, falsely flagging 36 entries | Replaced it with a paragraph-line check; final result is 38/38 complete, 0 duplicate or missing IDs. |
