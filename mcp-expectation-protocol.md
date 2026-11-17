# MCP Expectation Protocol

Status: Proposed design for discussion. No implementation authorized.

## Purpose

Before a tool participates in a task, the kernel needs an explicit record of what the tool accepts, what it can do, what its response means, and how the response may become task evidence.

The protocol has three scopes: a server profile, a contract for each exposed tool, and a task-specific expectation binding. A server can expose different kinds of operations. A tool whose behavior changes with arguments needs corresponding contract branches.

This is our proposed application protocol around MCP. It is not a claim that MCP itself provides these guarantees.

## 1. Server profile

Record server identity, connection and protocol details, authenticated account or principal, environment, inventory revision, discovery time, and inventory completeness. Reference the complete visible tool inventory established by the [onboarding invariants](mcp-tool-onboarding-invariants.md).

## 2. Per-tool expectation contract

| Contract part | What must be recorded |
|---|---|
| Identity and version | Exact exported tool name, supplying server, contract revision, and observed schema fingerprint. |
| Input interface | The server's declared input schema, required arguments, accepted values, and documented argument meaning. Preserve the original interface. |
| Effects | Expected reads, writes, deletions, notifications, or other effects, including argument-dependent behavior. Unknown effects remain explicit. |
| Preconditions | Required authorization, resource scope, relevant entity state, and logical constraints. Specify which conditions the kernel can check and which require backend enforcement. |
| Output interface | The declared output schema when available; otherwise explicitly record its absence. Record response forms, error indicators, and completeness or pagination signals. |
| Result meaning | Whether a response reports completed work, acknowledges a request, returns observations, or supplies a handle for pending work. |
| Ontology interpretation | Field mappings to entity types, namespaced identities, relationships, values, and units. Keep inferred mappings provisional until validated. |
| Evidence provenance | Source identity, call reference, source revision or snapshot when available, observation time, and original-response reference. |
| Freshness capability | Whether the source supports current reads, revisions, conditional writes, snapshots, or other consistency mechanisms. A recent fetch does not by itself establish recent source data. |
| Verification | How to establish the relevant postcondition, and what remains unverifiable. A tool's success report and an independently established outcome are different observations. |
| Failure and recovery | Known errors, retry conditions, idempotency support and scope, timeout handling, reconciliation, and any supported compensation. Never assume cancellation undoes an effect. |
| Bounds | Applicable call, time, size, pagination, token, and relationship limits. Distinguish locally enforceable limits from downstream behavior the kernel cannot bound. |
| Basis for expectations | Provider documentation, declared schemas, inspected implementation, or test evidence supporting each claim. Mark whether a guarantee is locally enforced, backend-supported, or unknown. |

The contract describes the external tool and our conditions for using it. It cannot manufacture capabilities the external service lacks.

## 3. Task-specific expectation binding

For each selected tool, the task records:

- The exact server and tool contract revision.
- Why the task needs the operation and which resources it may address.
- The required input evidence and its dependencies.
- The relevant output fields, entities, relationships, and claims.
- Applicable logical checks and freshness requirements at the point of use.
- The required postcondition and evidence for accepting it.
- What may continue if evidence is partial, and what must wait.
- Allowed recovery attempts within the existing task budget.

Only task-relevant output needs full ontology interpretation. Unmapped, irrelevant data does not prevent completion. Preserve original results separately from the selected task view.

## 4. Keep result assessments separate

| Assessment | Example states | Meaning |
|---|---|---|
| External execution | Not dispatched, reported success, reported error, pending, unknown | What is known about execution. An error may still follow partial effects. |
| Response contract | Conformant, nonconformant, undeclared | Whether the response meets the declared interface. |
| Ontology interpretation | Mapped, partially mapped, unresolved, contradictory | How much of the result can be interpreted and whether applicable constraints hold. |
| Task evidence | Sufficient, insufficient, stale, conflicted | Whether the relevant observations can support this task now. |
| Postcondition | Established, not established, unknown | Whether the required resulting state has been verified. |

A valid tool response can have a partial ontology mapping. A complete mapping can still contain stale evidence. A success acknowledgment can leave the postcondition unknown. These assessments must not be collapsed into one success flag.

## 5. Illustrative expectations by operation

These examples describe requirements, not capabilities verified for an actual server.

| Operation | Expected result | What the kernel needs to establish |
|---|---|---|
| Read a project | A project observation or a documented absence/error result | Requested identity, needed fields, source context, freshness, and completeness. |
| Create an assignment | A new assignment reference or an explicit pending outcome | Required relationships and creation outcome; supported deduplication before retrying uncertain requests. |
| Update an owner | An acknowledgment or updated representation, according to that tool's contract | Applicable preconditions, supported concurrency protection, and the required resulting ownership. |
| Delete an assignment | A deletion result or pending outcome | Whether deletion means removal, soft deletion, or another documented transition; evidence of that transition. |

Asynchronous completion is independent of read/write classification. When an operation returns a pending handle, record how completion can be observed and under whose authority. Do not mark it complete merely because the initial call returned.

## Relationship to the locked operators

The [nine generic OaK operators](oak-nine-operators.md) remain unchanged. They may help retrieve, select, traverse, filter, or aggregate admitted observations. Tool admission, permission enforcement, freshness, verification, and recovery are separate runtime design responsibilities.

## References

- [MCP tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools): discovery, input schemas, optional output schemas, and tool results.
- [MCP tool annotations](https://modelcontextprotocol.io/specification/2026-07-28/schema#toolannotations): behavior annotations are hints, not standalone proof of behavior.

Contract field definitions and recovery rules remain proposed until reviewed with the user. No implementation work proceeds while the design is being settled.
