# Demonstrations: ten ontology concepts

[Presentation](../README.md)

## Shared starting conditions

Each lesson used a synthetic input.
The runner sent one request to the installed Gemini CLI.
The runner withheld the reference answer from that request.
A deterministic checker evaluated the returned answer.

The main model reported by the CLI was `gemini-3.8-flash`.
The CLI also reported its `gemini-3.5-flash-lite` utility router.
The CLI executed no tools.

**Result:** All ten lessons passed their reference checks.
These lessons did not execute AppWorld tasks.

The tables describe submitted cases and returned answers.
A model answer does not mean that the described action executed.

## 01. Convert a statement to a triple

**Purpose:** Determine whether Gemini can record a positive relation without inventing a relation from a denial.

**Starting conditions:** The input stated that Maya maintains LoginService. It also stated that Maya does not maintain BillingService.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner submitted both statements. | Gemini received the same allowed vocabulary for both statements. | Only an explicitly asserted positive relation could produce a positive triple. |
| 2 | Gemini returned Maya → maintains → LoginService. | Gemini returned no positive triple for the BillingService statement. | A denial does not support a positive edge. |
| 3 | The checker compared the answer with the reference. | The answer passed. | The entity order, relation, and negative case matched the reference. |

**Limit:** The test used two supplied statements. It did not test general extraction from documents.

**Evidence:** [Input](../../learning-labs/01-triples/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/01-receipt.json).

## 02. Separate a graph update from an ontology update

**Purpose:** Determine whether Gemini can distinguish a new record from a new definition.

**Starting conditions:** The ontology already defined Person and Service. Update A added Noah as a Person. Update B added a TemporaryAssignment type with expiry.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner submitted the definitions and updates. | Gemini received two different changes. | An existing type can describe a new instance. |
| 2 | Gemini classified A as graph and B as ontology. | Both classifications matched the reference. | A adds a record. B adds a type and its meaning. |
| 3 | The checker evaluated the classifications. | The answer passed. | Each change belonged to the correct category. |

**Limit:** The model classified proposed changes. The test did not construct or install a new ontology.

**Evidence:** [Input](../../learning-labs/02-ontology-vs-facts/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/02-receipt.json).

## 03. Separate valid structure from supporting evidence

**Purpose:** Determine whether Gemini requires both valid structure and a supporting source record.

**Starting conditions:** The relation requires a Person as its subject and a Service as its object. The input supplied three candidate claims.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner supplied claim A with valid structure and no source receipt. | Gemini marked the structure valid and rejected admission. | Correct structure does not supply evidence. |
| 2 | The runner supplied claim B with the subject and object reversed. | Gemini marked the structure invalid and rejected admission. | The relation's type requirements were not satisfied. |
| 3 | The runner supplied claim C with valid structure and a matching receipt. | Gemini marked the structure valid and allowed admission. | Both required conditions were present. |
| 4 | The checker evaluated all three classifications. | The answer passed. | Only claim C met both conditions. |

**Limit:** These were synthetic source receipts. The test did not establish truth from a real external source.

**Evidence:** [Input](../../learning-labs/03-constraints-provenance/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/03-receipt.json).

## 04. Apply scope and expiry to an assignment

**Purpose:** Determine whether Gemini applies the environment and validity interval of an assignment.

**Starting conditions:** Maya had a Maintainer assignment for LoginService in Staging. The assignment started on November 1 and expired on November 20, 2026.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner asked about Staging on November 16. | Gemini returned Maya. | The environment and date matched the assignment. |
| 2 | The runner asked about Production on November 16. | Gemini returned an empty list. | A Staging assignment does not establish Production responsibility. |
| 3 | The runner asked about Staging on November 20. | Gemini returned an empty list. | The end date was exclusive. The assignment was no longer valid. |
| 4 | The checker evaluated the three answers. | The answer passed. | Each result matched the stated scope and date rule. |

**Limit:** An empty list meant no supporting assignment in the supplied input. It did not prove a global absence.

**Evidence:** [Input](../../learning-labs/04-relationship-entities/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/04-receipt.json).

## 05. Separate graph connectivity from authority

**Purpose:** Determine whether Gemini requires an approval rule and matching evidence.

**Starting conditions:** Maya and LoginService both belonged to Atlas. Approval required a current DeploymentApprover assignment for LoginService in Production.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner supplied case A without an approver assignment. | Gemini returned UNKNOWN. | Shared membership did not satisfy the approval rule. |
| 2 | The runner supplied case B with a matching current assignment. | Gemini returned SUPPORTED. | The required role, service, environment, and current status were present. |
| 3 | The checker compared both answers with the reference. | The answer passed. | The model did not treat a graph path as permission. |

**Limit:** The input supplied the rule and facts. The test did not discover authority rules automatically.

**Evidence:** [Input](../../learning-labs/05-traversal-inference/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/05-receipt.json).

## 06. Request a missing value

**Purpose:** Determine whether Gemini selects the documented read operation for a missing fact.

**Starting conditions:** The owner of LoginService was unknown. The input described get_service and set_owner.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner requested the service owner. | Gemini received an unknown value and two tool contracts. | The missing value required evidence acquisition. |
| 2 | Gemini returned a get_service request for LoginService. | The request used the required service identifier. | A read could obtain the owner. A write would change the owner. |
| 3 | The checker evaluated the request. | The request passed. No external tool executed. | A valid proposal is different from a completed read. |

**Limit:** This lesson measured request selection. It did not retrieve or verify the owner.

**Evidence:** [Input](../../learning-labs/06-model-consumption/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/06-receipt.json).

## 07. Apply an action precondition

**Purpose:** Determine whether runtime checks control an action independently of the model's proposal.

**Starting conditions:** Both cases requested deployment of LoginService to Production. Case A had no approval. Case B had matching current approval with a source receipt.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | Gemini returned the requested deploy call for each case. | Both proposals had the same action and arguments. | The model's proposal did not determine permission. |
| 2 | The local runtime evaluated case A. | The local deployed value remained false. | The required approval was absent. |
| 3 | The local runtime evaluated case B. | The local deployed value became true. | The supplied approval satisfied the precondition. |
| 4 | The checker evaluated the proposals and local outcomes. | The lesson passed. | The gate allowed only the supported case. |

**Limit:** The effect was a local test value. No real service deployment occurred.

**Evidence:** [Input](../../learning-labs/07-runtime-enforcement/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/07-receipt.json).

## 08. Mark dependent results as stale

**Purpose:** Determine whether Gemini identifies results that depend on a revoked fact.

**Starting conditions:** Decision8 depended on assignment17. Plan3 depended on decision8. A display name depended on a separate profile.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner supplied assignment17 at revision 2 with active status false. | The previous assignment support no longer applied. | A changed source can invalidate dependent results. |
| 2 | Gemini marked decision8 and plan3 as stale. | Gemini left the unrelated display name unchanged. | The dependency path reached both results but did not reach the display name. |
| 3 | Gemini returned false for execution of plan3. | The checker accepted the answer. | A plan based on revoked support must not execute. |

**Limit:** The input supplied all dependencies. The test did not discover missing or hidden dependencies.

**Evidence:** [Input](../../learning-labs/08-fact-invalidation/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/08-receipt.json).

## 09. Convert a record without inventing values

**Purpose:** Determine whether Gemini preserves known values during a proposed representation change.

**Starting conditions:** The old record contained Maya, LoginService, and receipt1. The new record shape also required environment and expiry fields.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | The runner supplied the old record and new shape. | No source value supported environment or expiry. | A new field does not create a fact. |
| 2 | Gemini preserved Maya, LoginService, and receipt1. | Gemini returned null for environment and expiry. | Known values remained unchanged. Unsupported values remained unknown. |
| 3 | The checker evaluated the proposed record. | The answer passed. | The conversion preserved evidence and did not invent defaults. |

**Limit:** Gemini proposed a record. The test did not install an ontology extension or migrate a live database.

**Evidence:** [Input](../../learning-labs/09-ontology-extension/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/09-receipt.json).

## 10. Apply versioned meanings

**Purpose:** Determine whether Gemini applies each rule version and retains the active episode's version.

**Starting conditions:** Version 1 allowed project or service approval. Version 2 required service approval. The available approval covered only the project.

| Step | Recorded action | Observed result | Logic |
| --- | --- | --- | --- |
| 1 | Gemini evaluated the approval under version 1. | Gemini returned permitted. | Version 1 accepted project approval. |
| 2 | Gemini evaluated the same approval under version 2. | Gemini returned not permitted. | Version 2 required service-specific approval. |
| 3 | Gemini selected versions for the two episodes. | The active episode kept version 1. A new episode used the externally accepted version 2. | The active episode retained its pinned version. |
| 4 | The checker evaluated all four fields. | The answer passed. | The result matched the supplied rules and version policy. |

**Limit:** The input assumed external acceptance of version 2. The experiment did not perform package promotion or test emergency revocation.

**Evidence:** [Input](../../learning-labs/10-semantic-version-change/gemini-input.json). [Original response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/10-receipt.json).

## Shared limits

These are exposed teaching cases.
The definitions and rules were supplied.
Ten correct answers do not establish general model reliability.
The suite did not construct ten complete domain ontologies.
The suite did not promote an ontology change.

[Suite result](../../learning-labs/gemini-results/20261116T183611.251922Z/summary.json).
[Original report](../../learning-labs/GEMINI-RESULTS.md).
[Deterministic companion results](../../learning-labs/RESULTS.md).

The separate [model-access demonstrations](../04-model-consumption/README.md) compare different interfaces.
