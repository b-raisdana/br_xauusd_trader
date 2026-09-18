# Test Plan: on_init.py Validation

## Objective

Validate initialization and smoke test behavior with extracted utility functions.

## Scope

- New utility functions for numerical comparisons
- Modified initialization code using utility functions
- Unchanged: initialization flow, lifecycle types, settings (documented as not applicable)

## Test Data

No external test data needed. Tests use inline values covering:
- Exact equality
- Within tolerance
- Outside tolerance
- Edge cases: zero, negative, very small, large numbers

## Test Cases

### Utility Function Tests

| Test | Input | Expected |
|------|-------|----------|
| Exact equal | Equal values | True |
| Within tolerance | Close values | True |
| Outside tolerance | Divergent values | False |
| Zero comparison | Near-zero values | True |
| Negative values | Negative inputs | True |
| Large values | Very large inputs | False (relative) |
| Custom tolerance | Custom tolerance | True/False |

### Integration Tests

1. **Smoke test passes** - Run existing smoke tests and verify all validations produce expected outcomes
2. **No behavioral change** - Compare results before/after extraction
3. **Utility function** - Verify utility function compiles correctly

## Approach

1. Create utility module with comparison functions
2. Update initialization code to use utility module
3. Run targeted tests
4. Run full test suite
5. Verify no behavioral changes

## Acceptance Criteria

- Utility module created with required functions
- Initialization code uses utility functions
- All existing smoke test vectors pass
- Unit tests pass with edge cases
- Full test suite passes
- No behavioral changes to initialization logic
