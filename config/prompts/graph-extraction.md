Extract all facts expressible under the supplied schema from the actual evidence
documents in this bounded chunk. Return
{entities:[{type,properties,source_ids:[document_id]}],
relations:[{relation,source_type,source_key,target_type,target_key,source_ids:[document_id]}],
ignored:[{document_id,reason}]}.

Every input document must appear in entity or relation source_ids, or in ignored
with an explicit reason. Do not fabricate properties or keys. Missing optional
values may be omitted. Use actual numeric values and ISO strings for dates.
Retain source units; any necessary conversion must follow the declared property
description. Use supplied stable source IDs as identity only when the schema
declares a source identifier. Local d0/d1 aliases are citation IDs, never stable
entity keys. Return actual records, never an extraction program. Do not revise
the schema or create relationships unsupported by the supplied evidence.

For repeated record types, use
entity_tables:[{type,columns:[property_name],rows:[{values:[actual_value],source_ids:[document_id]}]}]
instead of entities to reduce repetition. Each values array must align exactly
with columns. Use an empty entities or entity_tables list when using the other
format. Preserve the same schema types, property values, and citations in either
representation.

When previous_validation_error is supplied, correct that extraction defect
using the same schema and source evidence. Missing evidence remains missing;
do not invent a value or endpoint to satisfy a validator.

Choose compact stable semantic primary keys from the declared identity fields,
such as source-native entity identity and record scope. Do not copy a long
receipt hash into every primary key unless that hash is explicitly required by
the frozen schema. Cite source evidence with the supplied short document aliases;
the executor restores original receipt provenance without repeated model output.
