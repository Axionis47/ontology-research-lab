# Standards map, checked November 16, 2026

There is no single ontology-agent industry standard. The following specifications address different layers. They are useful interoperable building blocks, not evidence that every agent framework uses them.

| Mechanism | Primary specification | What it provides | What it does not provide |
| --- | --- | --- | --- |
| Graph statements | [RDF 1.1 Concepts](https://www.w3.org/TR/rdf11-concepts/) and [Primer](https://www.w3.org/TR/rdf11-primer/) | Subject/predicate/object model, IRIs and literals | Truth verification or action permission |
| Readable serialization | [Turtle](https://www.w3.org/TR/turtle/) | A concrete text syntax for RDF | Natural-language extraction |
| Vocabulary | [RDF Schema](https://www.w3.org/TR/rdf-schema/) | Classes, properties, subclassing, domain and range | Closed-world input rejection |
| Formal ontology | [OWL 2 Primer](https://www.w3.org/TR/owl2-primer/) | Formal meaning, class relationships and logical consequences | A workflow executor or truth oracle |
| Graph queries | [SPARQL 1.1 Query](https://www.w3.org/TR/sparql11-query/) | Graph-pattern matching, joins, filters and aggregation | Permission to perform external actions |
| Graph validation | [SHACL](https://www.w3.org/TR/shacl/) | Shapes that check conditions on a data graph | Evidence authenticity or universal real-world completeness |
| Provenance | [PROV-O](https://www.w3.org/TR/prov-o/) | Vocabulary for entities, activities, derivation and responsibility | Automatic freshness or dependency invalidation |
| JSON contracts | [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core) | Description and validation vocabulary for JSON structures | Domain truth, authorization, or ontology reasoning |
| Conditional HTTP write | [RFC 9110, If-Match](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1) | A server-enforced condition based on representation tags | A substitute for a server implementing the condition |

RDF Schema, OWL 2, SPARQL and SHACL are W3C specifications; the RDF Primer is explanatory guidance. JSON Schema 2020-12 is a published JSON Schema specification, not a W3C Recommendation or a finalized IETF RFC. RFC 9110 is an IETF Internet Standard. Pinning packages, release gates, actor budgets, and our three-state TRUE/FALSE/UNKNOWN policy are application design choices.

## The most important semantic trap

In RDFS, `maintains rdfs:domain Person` allows a reasoner to infer that a subject using `maintains` is a Person. It is not equivalent to rejecting a subject without an explicitly stored Person type. The latter is a validation policy, which can be expressed using SHACL with a chosen inference configuration.

Similarly, absence of an approval triple does not prove that approval is false everywhere. An execution policy can still refuse an action until current approval evidence is established. Unknown knowledge and denied execution are compatible.

## When definitions change

OWL supports ontology identity and version-related annotations. Those identifiers do not migrate a database or prove backward compatibility. We explicitly test old queries, new queries, preserved evidence, unsupported defaults, and changes in permitted behavior. A valid extension can still break an application if its queries or action bindings assume a different representation.

The lesson implementations deliberately keep the algorithm readable. Use their companion standards files to see the corresponding vocabulary and syntax, but do not claim an OWL reasoner or a SHACL engine ran unless a receipt explicitly records one.
