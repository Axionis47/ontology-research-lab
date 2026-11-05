# Ontology semantics and validation evidence

The executable contract is `oak.ontology.SchemaSpec`; `schema_json_schema()` exposes that same contract for model prompts. This document explains its semantics, not a second record definition. It resolves paper GAP-01. The paper requires lightweight schemas translated to OWL and checked with HermiT, but does not supply the grammar or axiom mapping.

## Exact mapping

| Schema declaration | OWL axiom or treatment |
| --- | --- |
| Entity type | Named `owl:Class` |
| `parents` | `rdfs:subClassOf` assertions; inheritance cycles are outside the supported grammar |
| `disjoint_with` | Pairwise `owl:disjointWith` through Owlready2 `AllDisjoint` |
| Local data property | Named `owl:DatatypeProperty`, scoped by declaring entity type, with that class as domain |
| Data-property type | `string`: xsd:string; `integer`: xsd:integer; `number`: xsd:decimal via Owlready2 float mapping; `boolean`: xsd:boolean; `date_time`: xsd:dateTime |
| `functional` data property | `owl:FunctionalProperty`; scalar in explicit graph records |
| Nonfunctional data property | Values are represented as a list in explicit graph records |
| Required data property | Qualified minimum cardinality 1 over the declared datatype |
| Primary key | Required functional data property plus a separate per-type graph uniqueness rule; no `owl:hasKey` or unique-name assumption |
| Relation | Named `owl:ObjectProperty` with declared domain and range |
| Relation characteristic | Corresponding OWL Functional, InverseFunctional, Transitive, Symmetric, Asymmetric, Reflexive, or Irreflexive property axiom |
| `inverse_of` | `owl:inverseOf`; endpoint declarations must be reciprocal |
| `some` restriction | Existential restriction with the specified filler |
| `only` restriction | Universal restriction with the specified filler |
| `min`, `max`, `exact` | Qualified cardinality restriction with the specified filler and nonnegative cardinality |
| Description | `rdfs:comment`; does not become an executable logical rule |

Class and property IRIs are deterministic under the normalized schema hash. Data properties with the same field name on different declaring types remain distinct OWL properties. Inherited explicit-record fields must satisfy each applicable declaration. Relations refer to named entity types; data restrictions refer to a qualified `Type.property` and that property's declared datatype. Disjunctions, arbitrary equivalence expressions, property chains, value restrictions, keys-as-OWL-identity, and arbitrary imported axioms are not accepted by this lightweight grammar. Unknown fields fail at every level.

The bundled HermiT rejects xsd:date, which is outside the OWL 2 datatype map. Therefore `date` is rejected by the grammar. Calendar dates can be ISO 8601 lexical strings; any date-format constraint belongs to a separately configured data-layer check, not an implicit guarantee of the string type. `date_time` maps to the supported xsd:dateTime.

OWL 2 DL has additional global restrictions, including restrictions on cardinality over non-simple properties. Combinations outside HermiT's supported profile return reasoner errors. They are never silently ignored or reported as logically valid.

## Open-world reasoning and graph integrity

`validate_ontology` checks the encoded schema, without fabricating instance data. A required property does not mean OWL will reject an individual merely because an explicit triple is absent: the open-world semantics can satisfy its existence with an unknown value. Empty classes can also make an otherwise contradictory class definition coexist with a globally consistent ontology.

The report therefore separates:

- `consistent`: whether the whole ontology has a model.
- `unsatisfiable_classes`: named classes that cannot have an instance.
- `valid`: true only when HermiT establishes consistency and finds no named unsatisfiable classes.

OaK rejects an unsatisfiable schema class even when the ontology is globally consistent, following Appendix A. A reasoner timeout, parser failure, unsupported datatype, or missing pinned JVM is an error, never a validity pass.

`validate_graph_records` checks explicit node and edge records separately. It validates field shapes, source presence, required values, datatypes, node IDs, per-type primary-key uniqueness, declared relation endpoints, and explicit functional, inverse-functional, asymmetric, and irreflexive violations. It does not claim complete closed-world validation of every OWL restriction. Entailed symmetric or transitive edges need not already be materialized. It does not validate source truth, function behavior, or task success.

## Runtime and artifacts

Every schema translation creates a fresh Owlready2 `World` and closes it afterward. The default global world is never used. Rejected candidate axioms cannot leak into another validation.

The reasoner is the actual HermiT JAR bundled in the pinned Owlready2 distribution. A subprocess uses the project-local Java path from `toolchain-java.lock.json`, checks the installed version against the lock, and records the Java binary, lockfile and HermiT JAR hashes. It does not fall back to system Java. The installer is responsible for verifying the downloaded Java archive; runtime evidence reports that pinned archive digest and the actual executable digest separately.

A validation attempt retains the submitted and normalized schemas, RDF/XML, name-to-IRI translation, exact command, reasoner input, stdout, stderr, timestamps, duration, exit code, dependency versions, and report. Existing completed validation directories cannot be reused. The raw OWL helper expects the caller to supply local import files and retain their provenance. Schema-generated ontologies have no imports.

HermiT's CLI can return exit code zero after a parser failure. The implementation requires the explicit successful consistency statement and unsatisfiable-class report, in addition to the exit status, before reporting a pass. It does not enable `ignoreUnsupportedDatatypes`.

## Genuine test sources

The full W3C Wine and Food RDF/XML files are retained unchanged under `tests/fixtures/ontology`, with origin URLs, byte lengths, SHA-256 hashes and attribution in the manifest. These are public ontology examples from the W3C OWL Guide, not an OaK benchmark or generated task data.

Tests retain the full axiom closure. Execution copies map Wine's import to the local Food file and remove Food's redundant back-import to the root Wine ontology. This avoids import recursion in the bundled OWLAPI while keeping all logical axioms and canonical IRIs. The original files are unchanged. The derivation is recorded beside each test input.

The full original bundle is reasoned over by HermiT's OWLAPI parser. This avoids an observed Owlready2 0.51 RDF/XML parser behavior with the old files' trailing-hash `xml:base` plus `rdf:ID`, which otherwise produces doubled-hash identifiers. The lightweight schema translator uses Owlready2 with its own well-defined generated IRIs and is tested separately.

Negative controls are explicitly marked mutations of the genuine artifact: one introduces a named unsatisfiable class with no instances; another makes the existing populated Wine class impossible, producing global inconsistency. Separate schema translation checks project actual Wine/Winery/hasMaker declarations into the supported grammar, add an explicit technical RDF IRI identity field, and introduce controlled contradictory restrictions. This projection does not claim to preserve every axiom of the original ontology. Graph-integrity tests use actual winery identifiers from the source.

These tests establish runtime behavior of the schema and reasoner boundary. They do not establish ontology quality for Coffee, USGS, or any other task, and do not reproduce an OaK benchmark score.

## Primary references

- [Paper, Section 3.2 and Appendix A](https://arxiv.org/pdf/2608.22974v1)
- [Owlready2 restrictions](https://owlready2.readthedocs.io/en/latest/restriction.html)
- [Owlready2 reasoning](https://owlready2.readthedocs.io/en/latest/reasoning.html)
- [W3C OWL Guide](https://www.w3.org/TR/2004/REC-owl-guide-20040210/)
