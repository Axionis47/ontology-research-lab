Draft only schema S matching the supplied schema contract. Use the requirement
analysis, declared scope, registered capability contracts, actual observations,
and previous schema when supplied. The task is to represent needed facts and
constraints, not to compose functions or certify task success.

Use meaningful domain entities and properties supporting the public tasks,
not opaque tool-result blobs. Keep representations that support execution,
validation, or inspection. Larger schemas are not an objective. Avoid redundant
concepts while preserving distinctions needed by the supplied obligations.
Choose stable identities scoped to observed location, time, or source where
needed. Do not encode particular answers or task IDs. Follow documented
datatype names and the authoritative schema contract.

Each tool response is extracted and validated as a separate graph fragment
before merging. Require only grounded identity and fields supported across
relevant input variants. Properties available only from another capability
response, or descriptive metadata absent under another documented input route,
must remain optional. Do not require a fragment to invent an absent field or an
edge endpoint available only in an earlier response. Task-specific completeness
obligations are distinct from general schema rules and are not enforced by this
fragment extractor.

Represent only constraints supported by task requirements or independent
evidence. A repeated call order is not proof of a prerequisite. Descriptions do
not create executable OWL axioms. The application validates the supported
schema-to-OWL mapping using HermiT; logical consistency does not establish
complete records, extraction accuracy, function correctness, or task coverage.

When validation_feedback is supplied, repair the reported schema defect while
preserving grounded requirements and valid declarations. Do not claim that your
repair passed validation; the application will run the check.
