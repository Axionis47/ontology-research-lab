# Actual Gemini comparison

Run directory: `20261116T192506.786593Z`. Models reported: gemini-3.5-flash-lite, gemini-3.8-flash.

Same task: choose the eligible production approver for LoginService. Maya is the author, Rin covers staging, Tao is expired, and Noah is eligible at revision 1. Forty unrelated assignments are present in the source world.

## Measured token use

| Interface | CLI calls | Main input tokens | Main generated tokens | Router total tokens | All-model total tokens | Answer | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| full_text | 1 | 9,571 | 2,985 | 5,388 | 17,944 | Noah | MEASURED |
| full_structured | 1 | 8,931 | 1,204 | 4,858 | 14,993 | Noah | MEASURED |
| retrieved_fragment | 1 | 6,401 | 1,149 | 2,442 | 9,992 | Noah | MEASURED |
| graph_queries | 3 | 19,109 | 3,285 | 6,878 | 29,272 | Noah | MEASURED |
| typed_function | 2 | 12,591 | 1,227 | 4,442 | 18,260 | Noah | MEASURED |

Counts are summed from Gemini CLI's actual statistics across each interface's calls. Main generated includes visible candidate tokens and reported thinking tokens. Router total includes its own input and generated tokens. All-model totals are provider-reported totals, not monetary cost. Repeated calls resend application history and incur CLI system/routing overhead. Character counts below describe only submitted user prompts, not hidden CLI context.

## Which stopped the stale action?

After selection, Noah's assignment was revoked. Revision 2 has no eligible candidate. Each model's identical recorded proposal was tested through an unguarded and a gated local fixture.

| Interface | Unguarded selected person | Unguarded violation | Gate admitted action | Gate reason |
| --- | --- | --- | --- | --- |
| full_text | Noah | True | False | STALE_OR_INELIGIBLE |
| full_structured | Noah | True | False | STALE_OR_INELIGIBLE |
| retrieved_fragment | Noah | True | False | STALE_OR_INELIGIBLE |
| graph_queries | Noah | True | False | STALE_OR_INELIGIBLE |
| typed_function | Noah | True | False | STALE_OR_INELIGIBLE |

The gate, not a particular context format, checks freshness before acting. This is a deterministic local effect test using actual model proposals. It does not mean the model saw the revocation or that it made an incorrect decision from revision 1. No external action ran, and no recovery model call was measured after rejection.

## Exact context at each call

- full_text, call 1: [exact submitted prompt](results/20261116T192506.786593Z/contexts/full_text-01.txt), 11,238 characters.
- full_structured, call 1: [exact submitted prompt](results/20261116T192506.786593Z/contexts/full_structured-01.txt), 9,354 characters.
- retrieved_fragment, call 1: [exact submitted prompt](results/20261116T192506.786593Z/contexts/retrieved_fragment-01.txt), 1,904 characters.
- graph_queries, call 1: [exact submitted prompt](results/20261116T192506.786593Z/contexts/graph_queries-01.txt), 1,537 characters.
- graph_queries, call 2: [exact submitted prompt](results/20261116T192506.786593Z/contexts/graph_queries-02.txt), 1,784 characters.
- graph_queries, call 3: [exact submitted prompt](results/20261116T192506.786593Z/contexts/graph_queries-03.txt), 2,749 characters.
- typed_function, call 1: [exact submitted prompt](results/20261116T192506.786593Z/contexts/typed_function-01.txt), 1,505 characters.
- typed_function, call 2: [exact submitted prompt](results/20261116T192506.786593Z/contexts/typed_function-02.txt), 2,013 characters.

All responses and observations are in the [original summary](results/20261116T192506.786593Z/summary.json) and sibling per-interface JSON files. [Manifest](results/20261116T192506.786593Z/manifest.json) pins source hashes, policy, configuration and limits.

## Interpretation limits

This is one exposed synthetic task, not an accuracy benchmark. A smaller prompt is not automatically a cheaper overall interaction: extra calls and system context also cost tokens. Retrieval coverage is trusted here, and the typed function implements these specific rules. Results do not establish arbitrary ontology construction, full RDF reasoning, native AppWorld performance, or production safety. See [the protocol definitions and limitations](README.md).
