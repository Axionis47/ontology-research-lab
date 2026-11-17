# MCP Tool Onboarding Invariants

Status: Working design. No implementation authorized.

User-established requirement: Each onboarded MCP server must have an explicit inventory of its tools. Each task must explicitly identify the tools included for that task and the server supplying each tool.

## Components and their boundaries

| Component | Responsibility |
|---|---|
| MCP server | Exposes a discoverable collection of named tools. |
| MCP tool | Defines one callable interface with arguments and a result contract. A call invokes that interface with particular arguments. |
| Typed domain function | Implements a domain procedure that may be exposed through an MCP tool. |
| Generic operator library, O | Supplies the nine locked primitives used to construct domain functions. The library itself is not automatically a tool. |
| Kernel | Tracks inventories, task bindings, contracts, permissions, and evidence around admitted calls. |

For functions built using OaK, the proposed relationship is: MCP server exposes tools; a tool invokes a typed domain function; that function composes, specializes, or adapts operators from the library. External MCP tools retain their own implementations and contracts. They do not have to be rewritten using OaK operators.

There is no required one-to-one relationship between tools and generic operators. The nine operators are not automatically nine MCP tools. A single dispatcher wrapping a whole library would be a separate interface design choice, not a consequence of using a library.

## Invariants

| ID | Invariant |
|---|---|
| MCP-01 | **Server identity is explicit.** Every onboarded connection records the server identity, supported protocol, account or principal, and environment. |
| MCP-02 | **Inventory precedes task admission.** Discover every tool visible under the recorded authorization context, including all discovery pages. Record incomplete discovery as incomplete; never present it as a complete inventory. |
| MCP-03 | **Every inventoried tool has a record.** Preserve its exact exported name, description, input schema, declared output schema when present, and relevant metadata. Record a missing output schema explicitly. |
| MCP-04 | **Tool identity includes its server.** Identically named tools from different servers remain distinct. Account and environment bindings prevent ambiguous execution. |
| MCP-05 | **Each task has an explicit tool manifest.** List every participating server and the exact tools selected from each server, with the contract revision or fingerprint and the task purpose. A tool cannot be included merely because its server is connected. |
| MCP-06 | **Task selection grants no extra authority.** An executed call must belong to the task manifest and satisfy current authorization, resource scope, and applicable limits. Inventory membership alone grants no execution permission. |
| MCP-07 | **External contracts are preserved.** Forward admitted arguments according to the tool's actual interface. Keep original results separate from task-specific projections and ontology interpretations. An incomplete mapping does not by itself make a valid tool response invalid. |
| MCP-08 | **Changes require reconciliation.** New tools are not silently added to existing tasks. Removed tools become unavailable. Relevant changes to names, schemas, permissions, or known behavior require revalidation of affected task bindings before further use. |
| MCP-09 | **No silent substitution.** If a selected tool is unavailable or unsuitable, record the affected task dependency. Selecting another tool requires an explicit manifest revision and compatibility checks. |
| MCP-10 | **Bindings survive context loss.** Persist inventories, task manifests, revisions, and operation receipts outside the prompt. Recheck current availability and authority when resuming. |
| MCP-11 | **Inventory and prompt contents are separate.** The kernel retains the complete discovered inventory. The model receives the relevant tool definitions for its current work, within the context budget. |
| MCP-12 | **Operator membership stays fixed.** MCP onboarding does not add, remove, rename, or redefine members of the locked nine-operator library. |

## Meaning of complete inventory

Completeness is relative to a particular server, authorization context, and discovery time. It does not mean discovering tools hidden from that account. If the server cannot supply a consistent snapshot across discovery pages, record that limitation and reconcile detected changes before relying on the inventory. A schema fingerprint identifies observed metadata; it cannot prove that remote implementation behavior has not changed.

## Illustrative task manifest

These names are examples, not tools discovered from an actual server.

| Task | Server | Selected tool | Purpose |
|---|---|---|---|
| Identify Atlas's owner | Project catalog | `get_project` | Obtain the project's owner reference. |
| Identify Atlas's owner | People directory | `get_person` | Resolve the owner reference to a person. |

Other discovered tools remain in the inventories but are not included in this task. For example, an available `update_project` tool is unnecessary for this read task.

## Sources and related decisions

- [MCP tools specification](https://modelcontextprotocol.io/specification/2026-07-28/server/tools): tool discovery, pagination, schemas, and changes to the available tool list. The numbered invariants above are our proposed kernel design requirements, not a verbatim list from MCP.
- [OaK, Section 3.2](https://arxiv.org/html/2608.22974v1#S3.SS2): composition of generic operators into typed domain functions.
- [Locked nine-operator baseline](oak-nine-operators.md).
- [Proposed MCP expectation protocol](mcp-expectation-protocol.md): per-server, per-tool, and per-task records of expected inputs, effects, results, and evidence handling.

Detailed execution contracts, freshness rules, dependency invalidation, and recovery behavior remain to be settled. This document does not authorize implementation.
