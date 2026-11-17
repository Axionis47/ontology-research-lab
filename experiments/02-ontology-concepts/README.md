# Ten ontology experiments, explained from input to result

[All experiment reports](../README.md) · [The complete AppWorld repair loop](../01-improvement-loop/README.md)

These ten lessons test individual building blocks. Each lesson supplied a small example to Gemini, received one JSON answer, and checked that answer in Python. They were not ten repair cycles. No failed lesson caused Gemini to rewrite an ontology or a function.

Read the [AppWorld report](../01-improvement-loop/README.md) for the recorded sequence in which a task failed, Gemini diagnosed it, a separate Gemini call authored a function repair, and later tasks passed.

## Understand the example before reading the results

Maya and Noah are fictional people. LoginService and BillingService are fictional software services. Atlas is a fictional project. These names are labels in supplied records.

Some lessons use a deployment example. A deployment means releasing software to an environment. **Staging** labels a testing environment; **Production** labels the live environment. In these lessons, both are strings in synthetic records. No real environment was contacted.

A **role assignment** says that a person has a particular responsibility for a service, possibly limited to an environment and a date range. An **approval record** is separate evidence that a requested action has approval. Neither is a database permission automatically enforced by storing the record.

An **ontology** defines what types, fields, relations, and rules mean. The **graph** contains particular people, services, and assignments. A **receipt** is a saved record of evidence or execution. A receipt in a synthetic input is manufactured test data; a model-run receipt records the actual request and response.

## The harness that ran all ten

Here, the harness is the Python program that prepares model inputs, invokes the model, checks its output, and saves evidence.

1. The runner loaded a lesson's definitions, concrete input, instruction, and required JSON shape.
2. It loaded the reference answer separately. That answer was withheld from the model prompt.
3. It sent one request to the installed Gemini CLI. The configured model routing and login were retained. CLI tools were disabled.
4. Gemini returned JSON. The runner parsed the response.
5. Python compared the required keys, value types, and field values with the reference. Lists representing answer sets could vary in order; the positions inside a triple could not.
6. For lesson 7 only, Python also evaluated the proposed calls against approval records and computed a local before/after deployment flag.
7. The runner saved the exact submitted prompt, returned CLI envelope, parsed answer, model identities, and checks.

The recorded November 16, 2026 run made ten lesson CLI invocations. Its reported main model was **gemini-3.8-flash**, with **gemini-3.5-flash-lite** as the utility router. All ten answers passed their reference checks. There were zero CLI tool calls.

The numbered steps below reconstruct inputs, outputs, and checker behavior. They do not claim to expose the model's private reasoning. Existing standalone Python demonstrations and the earlier Qwen interface comparison are separate experiments.

## 01. Convert a statement to a triple

**Question:** Can the model turn an explicitly positive sentence into a structured relationship without turning a negative sentence into a positive relationship?

A triple has three ordered parts: subject, relation, object. Here, “Maya maintains LoginService” becomes Maya → maintains → LoginService.

**Starting input:**

~~~text
Positive sentence: Maya maintains LoginService.
Negative sentence: Maya does not maintain BillingService.
Allowed vocabulary: Maya, LoginService, BillingService, maintains
~~~

**What happened:**

1. The runner sent both sentences and the allowed vocabulary in one prompt.
2. Gemini returned a positive triple for LoginService.
3. For the negative sentence, Gemini returned an empty positive-triple list.
4. Python checked the names, relation, ordering, and empty negative-case result against the reference.

**Recorded answer:**

~~~json
{"positive_triples":[["Maya","maintains","LoginService"]],"negative_sentence_positive_triples":[]}
~~~

**Result and repair status:** Passed. No repair or graph write occurred. This demonstrates the requested extraction on two sentences. It does not verify the sentences against an external source or implement a general document extractor.

[Submitted input](../../learning-labs/01-triples/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/01-receipt.json)

## 02. Separate a graph update from an ontology update

**Question:** Does observing a new person require changing the definition of a person?

**Starting input:**

~~~text
Existing types: Person, Service
Existing relation: maintains connects Person to Service

Update A: Observe that Noah is a Person.
Update B: Add a TemporaryAssignment type with an expiry property.
~~~

**What happened:**

1. The runner supplied the existing vocabulary and both proposed changes.
2. Gemini classified A as a graph update. Person already existed, so Noah could be represented as another instance of that type.
3. Gemini classified B as an ontology update. TemporaryAssignment introduced a definition that was absent from the supplied vocabulary.
4. Python checked both labels.

**Recorded answer:**

~~~json
{"A":"graph","B":"ontology"}
~~~

**Result and repair status:** Passed. These were classifications. The harness did not insert Noah into a database or install TemporaryAssignment. No revised ontology was used by a later task.

[Submitted input](../../learning-labs/02-ontology-vs-facts/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/02-receipt.json)

## 03. Separate valid structure from supporting evidence

**Question:** Should a correctly shaped claim be admitted when no source supports it?

The supplied rule said that maintains must connect a Person to a Service. Admission additionally required a source receipt that exactly matched the claim.

**Starting input:**

| Case | Proposed claim | Source supplied |
| --- | --- | --- |
| A | Maya → maintains → LoginService | None |
| B | LoginService → maintains → Maya | None |
| C | Maya → maintains → LoginService | A matching synthetic receipt |

**What happened:**

1. The prompt identified Maya as a Person and LoginService as a Service.
2. Gemini marked A structurally valid, but marked it unadmitted because the receipt was missing.
3. Gemini marked B structurally invalid: its subject was a Service and its object was a Person, reversing the required direction.
4. Gemini marked C structurally valid and admitted because both requirements were supplied.
5. Python checked all six boolean fields.

**Recorded answer:**

~~~json
{"A":{"structure_valid":true,"admitted":false},"B":{"structure_valid":false,"admitted":false},"C":{"structure_valid":true,"admitted":true}}
~~~

**Result and repair status:** Passed. The word admitted is a classification in the returned answer. No production graph writer accepted a fact. No repair ran, and the synthetic receipt did not establish real-world truth.

[Submitted input](../../learning-labs/03-constraints-provenance/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/03-receipt.json)

## 04. Apply scope and expiry to an assignment

**Question:** Can one assignment support responsibility in a different environment or after it expires?

A bare statement that Maya maintains LoginService omits where and when that responsibility applies. This lesson supplied those qualifiers explicitly.

**Starting record:**

~~~text
person: Maya
service: LoginService
role: Maintainer
environment: Staging
validFrom: 2026-11-01
validUntil: 2026-11-20
~~~

The rule included the start date and excluded the end date: validFrom <= query date < validUntil.

**What happened:**

1. Query A asked for Staging on November 16. The environment matched and the date fell inside the interval. Gemini returned Maya.
2. Query B asked for Production on November 16. The record said Staging, so Gemini returned an empty list.
3. Query C asked for Staging on November 20. That was the excluded end date, so Gemini returned an empty list.
4. Python checked the three lists.

**Recorded answer:**

~~~json
{"A":["Maya"],"B":[],"C":[]}
~~~

**Result and repair status:** Passed. Empty means no qualifying assignment was supplied. The test did not revoke a real person's access, enforce database roles, or repair a policy.

[Submitted input](../../learning-labs/04-relationship-entities/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/04-receipt.json)

## 05. Separate graph connectivity from authority

**Question:** Does sharing a project establish that someone may approve a deployment?

**Starting facts:**

~~~text
Maya → belongsTo → Atlas
LoginService → belongsTo → Atlas
~~~

Those records connect Maya to LoginService through Atlas. The separately supplied approval rule required a current DeploymentApprover assignment for LoginService in Production.

**What happened:**

1. Case A supplied the shared-project facts and no assignments.
2. Gemini returned UNKNOWN for A. Project membership supplied no matching approval-role assignment.
3. Case B added Maya's assignment with role DeploymentApprover, service LoginService, environment Production, and current=true.
4. Gemini returned SUPPORTED for B.
5. Python checked both labels.

**Recorded answer:**

~~~json
{"A":"UNKNOWN","B":"SUPPORTED"}
~~~

**Result and repair status:** Passed. The changed input supplied new authority evidence; no ontology or function was repaired. SUPPORTED is an answer about the fixture. It did not grant a storage credential or execute a deployment.

[Submitted input](../../learning-labs/05-traversal-inference/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/05-receipt.json)

## 06. Request a missing value

**Question:** When the owner is unknown, does the model request a read rather than inventing or changing the owner?

**Starting input:**

~~~text
Known record: LoginService has owner=UNKNOWN
Task: Identify the owner of LoginService.

get_service(service_id): returns service_id and owner
set_owner(service_id, person_id): changes the owner
~~~

These are tool contracts: descriptions of operation names, arguments, and results.

**What happened:**

1. The runner supplied the missing value and both contracts.
2. Gemini returned a get_service request using LoginService as the service_id.
3. Python compared the operation name and arguments with the reference.
4. The harness stopped after checking the proposal. It never called get_service, so no owner value was obtained.

**Recorded answer:**

~~~json
{"name":"get_service","arguments":{"service_id":"LoginService"}}
~~~

**Result and repair status:** Passed request-selection test. The underlying question about the owner remained unanswered. No repair ran. The [separate Qwen comparison](../04-model-consumption/README.md#a-qwen-used-three-interfaces) used different inputs and actual local record-return steps; its results must not be attributed to this Gemini lesson.

[Submitted input](../../learning-labs/06-model-consumption/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/06-receipt.json)

## 07. Apply an action precondition

**Question:** Can Python stop an unsupported action even when the model requests it?

Both cases asked to deploy LoginService to Production. Case A supplied no approval. Case B supplied an approval with service=LoginService, environment=Production, current=true, and source=receipt1.

**What happened:**

1. The prompt explicitly asked Gemini to produce the deploy request for both cases. This was intentional; the experiment was testing the external check.
2. Gemini returned the same operation and arguments for A and B.
3. Python checked that each proposal had exactly the expected shape.
4. Python separately checked the approval's presence, current flag, source, service, and environment.
5. It computed the local deployment flag shown below. No deployment API was called.

**Recorded model answer:**

~~~json
{"A":{"name":"deploy","arguments":{"service":"LoginService","environment":"Production"}},"B":{"name":"deploy","arguments":{"service":"LoginService","environment":"Production"}}}
~~~

**Recorded Python result:**

| Case | Before | Gate decision | After |
| --- | --- | --- | --- |
| A: approval missing | deployed=false | Deny | deployed=false |
| B: matching approval supplied | deployed=false | Allow | deployed=true |

**Result and repair status:** Passed. The gate was already implemented before the experiment. The run did not discover or repair it. The effect was a boolean in a local fixture, not storage-layer access enforcement or a real service deployment.

[Submitted input](../../learning-labs/07-runtime-enforcement/gemini-input.json) · [Response and gate outcomes](../../learning-labs/gemini-results/20261116T183611.251922Z/07-receipt.json) · [Checker implementation](../../learning-labs/gemini_experiments.py)

## 08. Mark dependent results as stale

**Question:** When one supporting fact changes, which recorded conclusions need to be checked again?

A dependency means that one result used another result as support.

**Starting input:**

~~~text
decision8 depends on assignment17
plan3 depends on decision8
display_name depends on profile1

Change supplied:
  assignment17 revision: 1 → 2
  assignment17 active_after: false
~~~

**What happened:**

1. The prompt supplied the revocation and all dependency links.
2. Gemini returned decision8 as stale because it depended directly on assignment17.
3. It also returned plan3 because the dependency continued through decision8.
4. It omitted display_name, whose dependency led to profile1.
5. It returned execute_plan3=false. Python checked the stale-node set and boolean.

**Recorded answer:**

~~~json
{"stale_nodes":["decision8","plan3"],"execute_plan3":false}
~~~

**Result and repair status:** Passed classification test. Gemini did not watch a live data source or update a stored plan. No function was repaired and no later execution was measured here. The [separate recovery report](../03-runtime-graph/README.md#b-a-graph-change-invalidated-an-action) shows the later experiment that actually returned rejection feedback to Gemini and requested a new computation.

[Submitted input](../../learning-labs/08-fact-invalidation/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/08-receipt.json)

## 09. Convert a record without inventing values

**Question:** If a new record format adds fields, what values can be carried over from the old evidence?

**Starting input:**

~~~text
Old record:
  person=Maya, service=LoginService, source=receipt1

New shape requires:
  person, service, environment, validUntil, source
~~~

A migration is a conversion between representations. Here, null means the source did not establish a value.

**What happened:**

1. The runner supplied the old record and new shape.
2. Gemini copied person, service, and source.
3. It returned null for environment and validUntil, because neither appeared in the supplied evidence.
4. Python checked every value and required that no extra fields appear.

**Recorded answer:**

~~~json
{"person":"Maya","service":"LoginService","environment":null,"validUntil":null,"source":"receipt1"}
~~~

**Result and repair status:** Passed. This was a proposed converted record. No live database migration or ontology extension was installed. There was no post-migration task run. Filling the new fields would require additional evidence.

[Submitted input](../../learning-labs/09-ontology-extension/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/09-receipt.json)

## 10. Apply versioned meanings

**Question:** What happens when the same evidence is evaluated under two different rules?

An episode is one task execution. A pinned version is the rule package that execution is bound to use.

**Starting input:**

~~~text
v1: Project approval OR service approval permits deployment.
v2: Only service-specific approval permits deployment.

Available approval: project only
Existing episode: pinned to v1
Version already accepted for new episodes: v2
~~~

**What happened:**

1. Gemini evaluated the project-only approval under v1 and returned true.
2. It evaluated that same approval under v2 and returned false.
3. It returned v1 for the existing episode and v2 for a new episode, following the supplied version policy.
4. Python checked all four fields.

**Recorded answer:**

~~~json
{"v1_permits":true,"v2_permits":false,"active_episode_version":"v1","new_episode_version":"v2"}
~~~

**Result and repair status:** Passed interpretation test. The prompt assumed that v2 had already been accepted. This run did not propose, test, promote, or execute a new package. The separate deterministic companion simulates candidate comparison; the [native AppWorld report](../01-improvement-loop/README.md) records a real model-authored function proposal and subsequent executions.

[Submitted input](../../learning-labs/10-semantic-version-change/gemini-input.json) · [Response and checks](../../learning-labs/gemini-results/20261116T183611.251922Z/10-receipt.json)

## What the ten results establish

All ten returned the expected answers on these supplied examples. The harness tested extraction, classification, rule application, request selection, and one local execution gate. It did not measure ten autonomous repair loops, storage RBAC, general ontology construction, or AppWorld performance.

The exact user prompts and original CLI responses are in the linked receipts. The CLI's own hidden context is not fully captured. Correct outputs on these small, exposed examples do not establish general reliability or an advantage over a no-ontology baseline.

To recheck the scorer without new model calls:

~~~sh
python3 -m unittest discover -s learning-labs -p test_gemini_experiments.py
~~~

The [runner instructions](../../learning-labs/GEMINI-START-HERE.md) explain how to prepare prompts or run new model trials. A new run gets its own evidence directory; it must not replace the original measurements.

[Suite result](../../learning-labs/gemini-results/20261116T183611.251922Z/summary.json) · [Model-run report](../../learning-labs/GEMINI-RESULTS.md) · [Deterministic companion results](../../learning-labs/RESULTS.md)
