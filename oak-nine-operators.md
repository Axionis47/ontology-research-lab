# OaK: Nine Public Operators

**Status: Locked design baseline.** Confirmed by the user on November 12, 2026.

This document fixes our generic operator library, O, to the nine operators below. Additions, removals, renaming, or changes to their intended roles require the user to explicitly reopen this decision. The alias `filter_categorical` names operator 5; it is not a tenth operator.

Source: Xiaohui Zhang et al., *Toward Effective and Reliable LLM Agents via Dynamic Ontology*, arXiv:2608.22974v1, August 24, 2026, [Appendix B: Generic Operator Library](https://arxiv.org/html/2608.22974v1#A2).

The names below follow the paper. Descriptions are paraphrased.

| # | Operator | Purpose |
|---|---|---|
| 1 | `extract_runtime_slots` | Uses an LLM to extract declared, typed parameters from a query, retaining explicit or strongly implied constraints and their evidence. |
| 2 | `lookup_entities` | Finds entities by type, ID, primary key, property values, or fuzzy name and text matching. Supports ranking and result limits. |
| 3 | `traverse_relations` | Explores relationships from starting entities, with specified relationship types, direction, and maximum hops. Returns visited entities and relationships. |
| 4 | `project_properties` | Selects requested properties into rows while retaining entity IDs, types, and primary keys. |
| 5 | `filter_property_categorical` | Keeps entities meeting categorical inclusion or exclusion conditions. The public alias is `filter_categorical`. |
| 6 | `filter_relation_connected` | Keeps entities connected to specified anchor entities through required relationship types. |
| 7 | `filter_numeric` | Applies numeric comparisons, thresholds, and interval conditions to properties. |
| 8 | `filter_set_overlap` | Filters multivalued properties using any-match, all-match, or minimum-overlap conditions. |
| 9 | `aggregate_values` | Calculates counts, sums, minima, maxima, or averages, optionally grouped by a field. |

## Design boundary

The lock covers operator membership, names, the documented alias, and intended roles. It does not claim that implementations exist in this workspace or that detailed execution contracts have been settled.

Task-specific typed functions, F, are a separate layer. They can compose, specialize, or adapt these operators into domain procedures. Designing those functions does not change the locked operator library.

Freshness checking, dependency invalidation, and recovery are separate design topics from our discussion. They are not additional operators in this list.

The proposed detailed input/output contracts, missing-value rules, provenance and runtime enforcement are now specified in [the domain computation document](docs/system/04-domain-and-surfaces.md) and its linked wire schemas. The operator membership, names and intended roles remain locked. This documentation update does not claim an implementation exists.
