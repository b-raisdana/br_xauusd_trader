Design a complete, practical testing strategy for this project's architecture and technology stack.

The project includes:

* CLI entry points and command-line workflows
* Application/service/use-case/domain/infrastructure layers
* Strong use of pandas, NumPy, Pandera, and vectorized data transformations
* DuckDB
* Apache Iceberg and data-storage/table abstractions
* External broker/exchange/market-data integrations
* Potentially stateful trading/data-processing workflows
* Plotly-based presentation, charts, and generated artifacts
* Configuration-driven behavior
* File-system and database I/O
* Async code and potentially blocking third-party APIs
* Git-based CI/CD and pre-commit validation
* Production-like data pipelines where silent numerical/data errors can be more dangerous than exceptions

### 1. Define the testing taxonomy

Identify which test categories are required and which are optional:

* Unit tests
* Characterization tests
* Regression tests
* Contract tests
* Property-based tests
* Parameterized tests
* Integration tests
* Component tests
* Smoke tests
* CLI tests
* End-to-end (E2E) tests
* Data-quality/schema tests
* Numerical/correctness tests
* Snapshot/golden-file tests
* Visualization tests
* Performance/benchmark tests
* Concurrency/async tests
* Failure/recovery/resilience tests
* External-system tests
* Security tests
* Installation/packaging tests

For every category, explain:

* What it protects against
* What should be tested
* What should NOT be tested at that level
* Typical test boundaries
* Dependencies that should be real vs mocked/faked
* Expected execution time
* When the test should run
* Whether it belongs in local development, pre-commit, PR CI, nightly CI, release CI, or production validation

### 2. Define the testing pyramid

Design an appropriate testing pyramid for this project.

Do not blindly apply the traditional "many unit tests, few E2E tests" model. Account for the fact that the project is heavily data-oriented and uses pandas/NumPy/Pandera/DuckDB/Iceberg and external market/broker systems.

Define the expected relative distribution of:

* Fast deterministic tests
* Component/data-processing tests
* Integration tests
* CLI tests
* E2E tests
* External-system tests

Explain where the testing pyramid should intentionally differ from a conventional web application.

### 3. Define coverage requirements

Define meaningful coverage targets rather than relying only on line coverage.

Specify required targets for:

* Overall line coverage
* Branch coverage
* New-code coverage
* Critical/domain logic coverage
* Data-transformation coverage
* Error/exception-path coverage
* CLI command coverage
* Configuration-path coverage
* Integration coverage
* Contract coverage

Distinguish between:

* Minimum acceptable coverage
* Required coverage for critical modules
* Recommended coverage
* Coverage that provides little additional value

Explain why 100% line coverage should or should not be required.

Also define how coverage should be enforced for:

* New code
* Modified code
* Legacy code
* Generated code
* Thin adapters
* CLI glue
* Visualization code
* Infrastructure code

### 4. Define testing strategy for pandas/NumPy/Pandera

Because the project is strongly based on dataframe/vectorized computation, explicitly define how to test:

* Index structure
* MultiIndex levels and names
* Index ordering
* Timezones and datetime precision
* Dtypes
* Missing values
* Duplicate rows
* Duplicate timestamps/ticks
* Sorting requirements
* Shape changes
* Column presence/order
* Pandera schemas
* Numerical transformations
* Vectorized calculations
* Rolling/expanding/shift/ewm operations
* GroupBy transformations
* Boundary conditions
* Empty dataframes
* Single-row dataframes
* Single-group data
* Multiple groups
* NaN/inf/-inf
* Floating-point tolerance
* Numerical stability
* Look-ahead/data leakage
* Stateful transformations

Define when to use:

* Exact equality
* `assert_frame_equal`
* Numerical tolerances
* Statistical/property-based assertions
* Golden/reference datasets

Define appropriate invariants for dataframe-based algorithms.

### 5. Define characterization and regression testing

Explain how characterization tests should be used when:

* Existing behavior is poorly documented
* Refactoring legacy/vectorized code
* Replacing loops with vectorized operations
* Replacing implementations without changing intended behavior
* Migrating storage engines
* Changing data-processing algorithms

Define how to distinguish:

* "Current behavior is preserved"
* "Current behavior is actually correct"

Do not allow characterization tests to accidentally freeze known bugs as permanent expected behavior.

Define a strategy for converting characterization tests into intentional regression tests.

### 6. Define testing for DuckDB and Iceberg

Specify the testing strategy for:

* SQL queries
* Query results
* Schema evolution
* Partitioning
* Snapshot/version behavior
* Reads/writes
* Data types
* Null semantics
* Timestamp semantics
* Transaction boundaries
* Concurrent access where applicable
* Table initialization
* Migration
* Corrupt/missing data
* Compatibility between application code and storage schemas

Define when to use:

* In-memory DuckDB
* Temporary DuckDB files
* Temporary Iceberg tables
* Test containers
* Real storage implementations
* Mocks/fakes

Tests must not depend on developer-specific local databases or persistent state.

### 7. Define external broker/exchange tests

Design a clear boundary between:

* Pure business/domain logic
* Broker/exchange adapters
* Market-data adapters
* Order/execution logic
* Network/API clients

Define:

* Unit tests with fakes
* Adapter/component tests
* Contract tests
* Integration tests against sandbox/testnet environments
* Limited live-environment smoke tests, if justified

Explicitly address:

* Timeouts
* Retries
* Rate limits
* Connection failures
* Partial responses
* Malformed responses
* Duplicate events
* Out-of-order events
* Reconnection
* Idempotency
* Order acknowledgement
* Execution/fill events
* Unknown broker states

Never make ordinary CI dependent on a live broker/exchange.

### 8. Define CLI testing

Test the CLI at multiple levels:

* Command parsing
* Argument validation
* Configuration loading
* Exit codes
* stdout
* stderr
* logging
* filesystem effects
* generated artifacts
* failure handling

Define when a CLI command should be tested through:

* Direct function invocation
* CLI runner
* Subprocess
* Full installed package

Include tests for:

* Invalid arguments
* Missing configuration
* Invalid configuration
* Missing files
* Permission failures
* Empty input
* Successful execution
* Partial failure
* Correct exit status

### 9. Define Plotly/presentation testing

Determine what should actually be tested in visualization code.

Cover:

* Data supplied to plots
* Trace count
* Trace types
* X/Y values
* Labels
* Axis configuration
* Filtering/grouping behavior
* Empty datasets
* Missing data
* Generated HTML/artifacts

Avoid brittle pixel-level testing unless there is a specific requirement.

Prefer testing the semantic structure of Plotly figures over exact serialized HTML when appropriate.

Define when snapshot testing is justified.

### 10. Define E2E workflows

Identify the smallest number of meaningful E2E scenarios that validate the complete system.

For example:

Input data
→ validation
→ transformation
→ storage
→ domain/service logic
→ presentation/output
→ CLI completion

Define E2E tests around real user/business workflows rather than individual implementation details.

Keep E2E tests deterministic and independent.

### 11. Define fixtures and test data

Design a test-data strategy covering:

* Tiny hand-crafted datasets
* Boundary datasets
* Realistic datasets
* Production-derived anonymized datasets
* Golden/reference datasets
* Random/property-based datasets
* Corrupted datasets
* Large datasets

Define fixture ownership, naming, location, lifecycle, and size limits.

Avoid unnecessarily large fixtures when a small deterministic fixture can expose the same behavior.

### 12. Define deterministic testing

Specify requirements for:

* Random seeds
* Time
* Timezones
* Current date
* UUIDs
* Network
* Filesystem paths
* Environment variables
* OS differences
* Locale
* Floating-point behavior
* External service responses

Tests should produce reproducible failures.

### 13. Define mocking/faking policy

Explicitly define what should be:

* Mocked
* Faked
* Stubbed
* Recorded
* Run against a real implementation

Avoid excessive mocking of internal implementation details.

Prefer testing against real implementations for important data/storage boundaries where the cost is reasonable.

### 14. Define failure and resilience testing

Test important failure modes including:

* Invalid input
* Schema violations
* Missing data
* Corrupt data
* Empty data
* Network timeout
* Connection loss
* API errors
* Partial writes
* Duplicate events
* Out-of-order events
* Disk/storage failure
* Interrupted processing
* Invalid configuration
* Dependency failure

Define which failures belong in normal CI and which belong in dedicated resilience/nightly testing.

### 15. Define performance and runtime budgets

Establish explicit budgets for every test layer.

Propose practical target limits such as:

* Individual unit test: milliseconds
* Unit-test suite: seconds
* Component/data tests: seconds to low minutes
* Integration suite: minutes
* E2E suite: limited number, minutes
* Full CI pipeline: bounded and predictable
* Nightly/extended tests: substantially larger budget

Define:

* Per-test timeout
* Per-suite timeout
* CI job timeout
* Maximum fixture size
* Maximum memory consumption
* Parallelization strategy
* When performance tests should run

Do not optimize tests merely for maximum speed; define a reasonable engineering trade-off between confidence and runtime.

### 16. Define test execution stages

Design a concrete execution matrix such as:

| Stage            | Tests | Target runtime | Required before merge |
| ---------------- | ----- | -------------: | --------------------- |
| Local/IDE        | ...   |            ... | ...                   |
| Pre-commit       | ...   |            ... | ...                   |
| PR fast CI       | ...   |            ... | ...                   |
| PR full CI       | ...   |            ... | ...                   |
| Main branch      | ...   |            ... | ...                   |
| Nightly          | ...   |            ... | ...                   |
| Release          | ...   |            ... | ...                   |
| Production smoke | ...   |            ... | ...                   |

Specify which tests are mandatory at each stage.

### 17. Define test implementation order

Define when each type of test should be introduced during development.

For example:

1. Establish critical domain invariants
2. Add characterization tests around existing behavior
3. Add unit tests for pure logic
4. Add data/schema tests
5. Add component/integration tests
6. Add CLI tests
7. Add external-system contract tests
8. Add minimal E2E workflows
9. Add regression cases for every discovered bug
10. Add performance tests when performance becomes a requirement

Explain when a developer should stop adding tests and consider the behavior sufficiently protected.

### 18. Define bug-to-test policy

Every production/CI bug should result in an appropriate regression test.

Define how to determine the lowest test level capable of reproducing the bug.

Prefer the lowest level that provides meaningful protection, while adding a higher-level regression test when the failure involved integration between components.

### 19. Define test quality criteria

Explain how to identify:

* Brittle tests
* Over-mocked tests
* Tests coupled to implementation details
* Duplicate tests
* Low-value coverage
* Slow tests
* Flaky tests
* Non-deterministic tests
* Tests that merely reproduce implementation
* Tests that cannot detect realistic regressions

Define a policy for quarantining, fixing, or removing flaky tests.

### 20. Define the final testing architecture

Produce a concrete testing architecture for this project, including:

* Recommended `tests/` directory structure
* Naming conventions
* Fixture organization
* Test markers
* Test configuration
* Coverage configuration
* Test data organization
* Unit/integration/E2E boundaries
* CI stages
* Runtime budgets
* Required coverage gates
* External dependency policy
* Test ownership

The result should be an actionable testing standard that can be adopted as a project-wide engineering policy, not merely a list of possible test types.

Optimize for:

* High confidence
* Determinism
* Fast developer feedback
* Meaningful coverage
* Low maintenance cost
* Realistic protection against data-processing and integration failures
* Clear separation between cheap tests and expensive tests
* No unnecessary testing of third-party libraries themselves
* No dependency on live external systems for ordinary development or PR validation
