"""Strict task-schema contracts, OWL translation, and real HermiT evidence.

The grammar resolves paper GAP-01 explicitly. OWL reasoning uses the open-world
assumption; ``validate_graph_records`` is a separate closed-record check. Each
reasoner invocation persists input, command, stdout, stderr, and a JSON report.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import re
import subprocess
import time
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import owlready2 as owl
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Datatype = Literal["string", "integer", "number", "boolean", "date_time"]
Characteristic = Literal[
    "functional",
    "inverse_functional",
    "transitive",
    "symmetric",
    "asymmetric",
    "reflexive",
    "irreflexive",
]
_DATATYPES = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "date_time": datetime,
}
_CHARACTERISTICS = {
    "functional": owl.FunctionalProperty,
    "inverse_functional": owl.InverseFunctionalProperty,
    "transitive": owl.TransitiveProperty,
    "symmetric": owl.SymmetricProperty,
    "asymmetric": owl.AsymmetricProperty,
    "reflexive": owl.ReflexiveProperty,
    "irreflexive": owl.IrreflexiveProperty,
}
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class StrictSpec(BaseModel):
    """Reject coercions and unrecognized fields in all schema structures."""

    model_config = ConfigDict(extra="forbid", strict=True)


class PropertySpec(StrictSpec):
    """Data property; nonfunctional properties use lists in graph records."""

    type: Datatype
    required: bool = False
    functional: bool = True
    description: str | None = None


class RestrictionSpec(StrictSpec):
    """A class restriction over a relation or qualified ``Type.property``."""

    property: str
    kind: Literal["some", "only", "min", "max", "exact"]
    filler: str
    cardinality: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def check_cardinality(self) -> RestrictionSpec:
        """Cardinality is required only for the three numerical constructors."""
        if (self.kind in {"min", "max", "exact"}) != (self.cardinality is not None):
            raise ValueError("cardinality is required exactly for min, max, and exact")
        return self


class EntityTypeSpec(StrictSpec):
    """Named class, its local data properties, and declared OWL constraints."""

    primary_key: str
    properties: dict[str, PropertySpec]
    parents: list[str] = Field(default_factory=list)
    disjoint_with: list[str] = Field(default_factory=list)
    restrictions: list[RestrictionSpec] = Field(default_factory=list)
    description: str | None = None


class RelationSpec(StrictSpec):
    """Object property with one domain, one range, and optional OWL flags."""

    source: str
    target: str
    characteristics: list[Characteristic] = Field(default_factory=list)
    inverse_of: str | None = None
    description: str | None = None


class SchemaSpec(StrictSpec):
    """Authoritative lightweight ontology grammar used in model prompts.

    Unknown fields fail, including unsupported OWL constructs. Property names
    are scoped to their declaring entity type. Primary keys are record identity
    rules; they are deliberately not translated into ``owl:hasKey``.
    """

    schema_version: Literal[1] = 1
    name: str = Field(min_length=1)
    entity_types: dict[str, EntityTypeSpec] = Field(min_length=1)
    relations: dict[str, RelationSpec] = Field(default_factory=dict)
    description: str | None = None

    @model_validator(mode="after")
    def check_references(self) -> SchemaSpec:
        """Resolve names before building any OWL or invoking the JVM."""
        for name, entity in self.entity_types.items():
            _check_name(name)
            for prop in entity.properties:
                _check_name(prop)
            if entity.primary_key not in entity.properties:
                raise ValueError(f"{name}: primary_key must name a local property")
            if not entity.properties[entity.primary_key].functional:
                raise ValueError(f"{name}: primary_key must be functional")
            for reference in entity.parents + entity.disjoint_with:
                if reference not in self.entity_types:
                    raise ValueError(f"{name}: unknown entity reference {reference!r}")
            if len(entity.parents) != len(set(entity.parents)):
                raise ValueError(f"{name}: duplicate parents")
        for name in self.entity_types:
            self.ancestors(name)  # Reject inheritance cycles, not logical contradictions.
        for name, relation in self.relations.items():
            _check_name(name)
            if relation.source not in self.entity_types or relation.target not in self.entity_types:
                raise ValueError(f"{name}: relation domain/range must be declared types")
            if len(set(relation.characteristics)) != len(relation.characteristics):
                raise ValueError(f"{name}: duplicate characteristics")
            if relation.inverse_of is not None:
                inverse = self.relations.get(relation.inverse_of)
                if inverse is None:
                    raise ValueError(f"{name}: unknown inverse relation")
                if (inverse.source, inverse.target) != (relation.target, relation.source):
                    raise ValueError(f"{name}: inverse domain/range must be reciprocal")
                if inverse.inverse_of not in (None, name):
                    raise ValueError(f"{name}: conflicting inverse declaration")
        for name, entity in self.entity_types.items():
            for restriction in entity.restrictions:
                if restriction.property in self.relations:
                    if restriction.filler not in self.entity_types:
                        raise ValueError(f"{name}: object restriction needs an entity filler")
                else:
                    parts = restriction.property.split(".")
                    if len(parts) != 2 or parts[0] not in self.entity_types:
                        raise ValueError(f"{name}: unknown restricted property")
                    prop = self.entity_types[parts[0]].properties.get(parts[1])
                    if prop is None or restriction.filler != prop.type:
                        raise ValueError(f"{name}: data restriction must use its declared datatype")
        return self

    def ancestors(self, name: str, trail: frozenset[str] = frozenset()) -> set[str]:
        """Return named ancestors, rejecting cycles in this supported grammar."""
        if name in trail:
            raise ValueError(f"inheritance cycle at {name}")
        result: set[str] = set()
        for parent in self.entity_types[name].parents:
            result.add(parent)
            result.update(self.ancestors(parent, trail | {name}))
        return result


def _check_name(name: str) -> None:
    if not _NAME.fullmatch(name):
        raise ValueError(f"invalid identifier {name!r}; use letters, digits, and underscores")


def parse_schema(schema: dict[str, Any] | SchemaSpec) -> SchemaSpec:
    """Validate a dict against the authoritative grammar, without coercion."""
    if isinstance(schema, SchemaSpec):
        # Revalidate mutable nested containers, rather than trusting a prior parse.
        schema = schema.model_dump(mode="json")
    return SchemaSpec.model_validate(schema)


def schema_json_schema() -> dict[str, Any]:
    """Return the same grammar used by parsing, suitable for structured prompts."""
    return SchemaSpec.model_json_schema()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve()), "sha256": _digest(path), "size_bytes": path.stat().st_size}


def schema_to_owl(schema: dict[str, Any] | SchemaSpec, output_path: str | Path) -> dict[str, Any]:
    """Translate supported declarations exactly, save RDF/XML, then close the World.

    Returns the stable schema-name to OWL-IRI mapping. This function does not
    reason and does not declare the resulting ontology valid.
    """
    spec = parse_schema(schema)
    schema_hash = hashlib.sha256(_json(spec.model_dump(mode="json")).encode()).hexdigest()
    world = owl.World()
    try:
        ontology = world.get_ontology(f"https://oak.local/schema/{schema_hash}#")
        classes: dict[str, Any] = {}
        properties: dict[str, Any] = {}
        with ontology:
            for name in spec.entity_types:
                classes[name] = types.new_class(f"type__{name}", (owl.Thing,))
            if spec.description:
                ontology.metadata.comment.append(spec.description)
            for name, entity in spec.entity_types.items():
                cls = classes[name]
                cls.label.append(name)
                if entity.description:
                    cls.comment.append(entity.description)
                cls.is_a.extend(classes[parent] for parent in entity.parents)
                for other in entity.disjoint_with:
                    owl.AllDisjoint([cls, classes[other]])
                for prop_name, declaration in entity.properties.items():
                    bases = (
                        (owl.DataProperty, owl.FunctionalProperty)
                        if declaration.functional
                        else (owl.DataProperty,)
                    )
                    prop = types.new_class(f"data__{name}__{prop_name}", bases)
                    prop.domain = [cls]
                    prop.range = [_DATATYPES[declaration.type]]
                    prop.label.append(f"{name}.{prop_name}")
                    if declaration.description:
                        prop.comment.append(declaration.description)
                    properties[f"{name}.{prop_name}"] = prop
                    if declaration.required or prop_name == entity.primary_key:
                        cls.is_a.append(prop.min(1, _DATATYPES[declaration.type]))
            for name, relation in spec.relations.items():
                bases = (
                    owl.ObjectProperty,
                    *(_CHARACTERISTICS[x] for x in relation.characteristics),
                )
                prop = types.new_class(f"relation__{name}", bases)
                prop.domain = [classes[relation.source]]
                prop.range = [classes[relation.target]]
                prop.label.append(name)
                if relation.description:
                    prop.comment.append(relation.description)
                properties[name] = prop
            for name, relation in spec.relations.items():
                if relation.inverse_of:
                    properties[name].inverse_property = properties[relation.inverse_of]
            for name, entity in spec.entity_types.items():
                for restriction in entity.restrictions:
                    prop = properties[restriction.property]
                    filler = (
                        classes[restriction.filler]
                        if restriction.property in spec.relations
                        else _DATATYPES[restriction.filler]
                    )
                    constructor = getattr(
                        prop, "exactly" if restriction.kind == "exact" else restriction.kind
                    )
                    axiom = (
                        constructor(filler)
                        if restriction.cardinality is None
                        else constructor(restriction.cardinality, filler)
                    )
                    classes[name].is_a.append(axiom)
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        ontology.save(file=str(destination), format="rdfxml")
        return {
            "schema_sha256": schema_hash,
            "classes": {name: cls.iri for name, cls in classes.items()},
            "properties": {name: prop.iri for name, prop in properties.items()},
            "owl": _artifact(destination),
        }
    finally:
        world.close()


def _resolve_java(lock_path: Path) -> tuple[Path, dict[str, Any]]:
    lock = json.loads(lock_path.read_text())
    java = (lock_path.parent / lock["install_directory"] / lock["java_relative_path"]).resolve()
    if not java.is_file():
        raise FileNotFoundError(f"pinned Java is absent: {java}")
    result = subprocess.run([str(java), "-version"], capture_output=True, text=True, timeout=15)
    version = result.stdout + result.stderr
    if result.returncode or lock["version"] not in version:
        raise RuntimeError(
            f"Java runtime does not match pinned version {lock['version']}: {version}"
        )
    return java, {
        "lock": _artifact(lock_path),
        "version_output": version,
        "binary": _artifact(java),
        "expected_archive_sha256": lock["sha256"],
    }


def validate_owl_file(
    owl_path: str | Path,
    artifact_dir: str | Path,
    *,
    java_lock_path: str | Path | None = None,
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    """Run bundled HermiT on a real OWL input and retain independent evidence.

    The directory must not already contain a validation report. Imported OWL
    files must be supplied locally by the caller. No unsupported-datatype
    suppression is enabled. ``consistent`` can coexist with unsatisfiable
    classes; ``valid`` requires both consistency and no named unsatisfiable class.
    """
    directory = Path(artifact_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / "validation.json").exists():
        raise FileExistsError(f"validation evidence already exists: {directory}")
    source = Path(owl_path).resolve()
    if timeout_seconds <= 0 or not math.isfinite(timeout_seconds):
        raise ValueError("timeout_seconds must be positive and finite")
    lock_path = (
        Path(java_lock_path).resolve()
        if java_lock_path
        else Path(__file__).resolve().parents[2] / "toolchain-java.lock.json"
    )
    started = time.monotonic()
    report: dict[str, Any] = {
        "schema_version": 1,
        "evidence_type": "owl_hermit",
        "started_at": datetime.now(UTC).isoformat(),
        "status": "error",
        "valid": False,
        "consistent": None,
        "unsatisfiable_classes": [],
        "errors": [],
        "command": None,
        "returncode": None,
        "owlready2_version": importlib.metadata.version("owlready2"),
        "coverage": "OWL logical consistency and named-class satisfiability only",
    }
    stdout = stderr = ""
    try:
        java, runtime = _resolve_java(lock_path)
        report["java"] = runtime
        jar = Path(owl.__file__).parent / "hermit" / "HermiT.jar"
        report["hermit_jar"] = _artifact(jar)
        target = directory / "reasoner-input.owl"
        if source != target:
            target.write_bytes(source.read_bytes())
        report["input"] = _artifact(target)
        command = [
            str(java),
            "-Xmx512M",
            "-cp",
            str(jar),
            "org.semanticweb.HermiT.cli.CommandLine",
            "-k",
            "-U",
            "-N",
            target.as_uri(),
        ]
        report["command"] = command
        (directory / "command.json").write_text(_json(command))
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
        stdout, stderr = completed.stdout, completed.stderr
        report["returncode"] = completed.returncode
        # HermiT's CLI can return zero for parse errors, so success requires its
        # explicit consistency statement and unsatisfiable-class listing.
        combined = stdout + "\n" + stderr
        if "Inconsistent ontology" in combined or (
            "http://www.w3.org/2002/07/owl#Thing is not satisfiable." in stdout
        ):
            report.update(status="inconsistent", consistent=False)
        elif (
            completed.returncode == 0
            and "http://www.w3.org/2002/07/owl#Thing is satisfiable." in stdout
            and "Classes equivalent to 'http://www.w3.org/2002/07/owl#Nothing':" in stdout
            and "It all went pear-shaped" not in combined
        ):
            tail = stdout.split(
                "Classes equivalent to 'http://www.w3.org/2002/07/owl#Nothing':", 1
            )[1]
            unsatisfiable = sorted(
                {
                    line.strip().strip("<>")
                    for line in tail.splitlines()
                    if line.startswith("\t") and line.strip().strip("<>") != owl.Nothing.iri
                }
            )
            report.update(
                status="unsatisfiable_classes" if unsatisfiable else "consistent",
                consistent=True,
                unsatisfiable_classes=unsatisfiable,
                valid=not unsatisfiable,
            )
        else:
            report["errors"].append("HermiT did not produce a complete successful reasoning result")
    except subprocess.TimeoutExpired as exc:
        report["status"] = "timeout"
        report["errors"].append(f"HermiT or Java exceeded its timeout: {exc.timeout} seconds")
        stdout = (
            exc.stdout.decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else exc.stdout or ""
        )
        stderr = (
            exc.stderr.decode(errors="replace")
            if isinstance(exc.stderr, bytes)
            else exc.stderr or ""
        )
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    (directory / "stdout.txt").write_text(stdout)
    (directory / "stderr.txt").write_text(stderr)
    report["stdout"] = _artifact(directory / "stdout.txt")
    report["stderr"] = _artifact(directory / "stderr.txt")
    report["duration_seconds"] = time.monotonic() - started
    report["finished_at"] = datetime.now(UTC).isoformat()
    report["report_path"] = str(directory / "validation.json")
    (directory / "validation.json").write_text(_json(report))
    return report


def validate_ontology(
    schema: dict[str, Any] | SchemaSpec,
    artifact_dir: str | Path,
    *,
    java_lock_path: str | Path | None = None,
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    """Persist a strict schema, translate in an isolated World, and run HermiT.

    Invalid input is retained with its validation errors. Existing validation
    directories cannot be overwritten. The returned ``valid`` flag is only an
    ontology check, not graph integrity, function correctness, or task success.
    """
    directory = Path(artifact_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise FileExistsError(f"use a new directory for each validation attempt: {directory}")
    source = schema.model_dump(mode="json") if isinstance(schema, SchemaSpec) else schema
    (directory / "schema-input.json").write_text(_json(source))
    try:
        spec = parse_schema(source)
        (directory / "schema.json").write_text(_json(spec.model_dump(mode="json")))
        translation = schema_to_owl(spec, directory / "ontology.owl")
    except (ValidationError, ValueError, TypeError) as exc:
        report = {
            "schema_version": 1,
            "evidence_type": "schema_structure",
            "status": "invalid_schema",
            "valid": False,
            "consistent": None,
            "unsatisfiable_classes": [],
            "errors": [str(exc)],
            "input": _artifact(directory / "schema-input.json"),
            "report_path": str(directory / "validation.json"),
        }
        (directory / "validation.json").write_text(_json(report))
        return report
    (directory / "translation.json").write_text(_json(translation))
    report = validate_owl_file(
        directory / "ontology.owl",
        directory,
        java_lock_path=java_lock_path,
        timeout_seconds=timeout_seconds,
    )
    report["schema"] = _artifact(directory / "schema.json")
    report["translation"] = _artifact(directory / "translation.json")
    (directory / "validation.json").write_text(_json(report))
    return report


class GraphNode(StrictSpec):
    """Serialized graph node interface shared with the extraction stage."""

    id: str = Field(min_length=1)
    type: str
    properties: dict[str, Any]
    sources: list[dict[str, Any]]


class GraphEdge(StrictSpec):
    """Typed directed edge; endpoint IDs must identify actual graph nodes."""

    source: str
    target: str
    relation: str
    sources: list[dict[str, Any]]


def _matches_datatype(value: Any, datatype: str) -> bool:
    if datatype == "string":
        return isinstance(value, str)
    if datatype == "integer":
        return type(value) is int
    if datatype == "number":
        return type(value) in (int, float) and math.isfinite(value)
    if datatype == "boolean":
        return type(value) is bool
    if not isinstance(value, str):
        return False
    try:
        return "T" in value and bool(datetime.fromisoformat(value))
    except ValueError:
        return False


def validate_graph_records(
    schema: dict[str, Any] | SchemaSpec,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check explicit graph records independently from OWL open-world reasoning.

    Checks record shapes, required data, datatypes, unique IDs/type-primary keys,
    declared relation endpoints, and explicit functional/asymmetric/irreflexive
    violations. It does not require entailed symmetric or transitive edges to be
    materialized and does not claim full closed-world OWL restriction validation.
    """
    spec = parse_schema(schema)
    errors: list[str] = []
    by_id: dict[str, GraphNode] = {}
    identities: set[tuple[str, str]] = set()
    parsed_edges: list[GraphEdge] = []
    for index, raw in enumerate(nodes):
        try:
            node = GraphNode.model_validate(raw)
        except ValidationError as exc:
            errors.append(f"node[{index}]: {exc}")
            continue
        if node.id in by_id:
            errors.append(f"duplicate node id: {node.id}")
        by_id[node.id] = node
        if node.type not in spec.entity_types:
            errors.append(f"{node.id}: undeclared type {node.type}")
            continue
        if not node.sources:
            errors.append(f"{node.id}: missing source provenance")
        scopes = [node.type, *sorted(spec.ancestors(node.type))]
        allowed = {key for scope in scopes for key in spec.entity_types[scope].properties}
        for key in node.properties.keys() - allowed:
            errors.append(f"{node.id}: undeclared property {key}")
        for scope in scopes:
            entity = spec.entity_types[scope]
            for key, declaration in entity.properties.items():
                value = node.properties.get(key)
                required = declaration.required or key == entity.primary_key
                if value is None:
                    if required:
                        errors.append(f"{node.id}: missing required property {scope}.{key}")
                    continue
                values = [value] if declaration.functional else value
                if not isinstance(values, list) or (required and not values):
                    errors.append(f"{node.id}: invalid cardinality for {scope}.{key}")
                elif any(not _matches_datatype(item, declaration.type) for item in values):
                    errors.append(f"{node.id}: invalid datatype for {scope}.{key}")
        primary_key = spec.entity_types[node.type].primary_key
        key_value = node.properties.get(primary_key)
        if key_value is not None and _matches_datatype(
            key_value, spec.entity_types[node.type].properties[primary_key].type
        ):
            identity = (node.type, _json(key_value))
            if identity in identities:
                errors.append(f"duplicate primary key for type {node.type}: {key_value!r}")
            identities.add(identity)
    for index, raw in enumerate(edges):
        try:
            edge = GraphEdge.model_validate(raw)
        except ValidationError as exc:
            errors.append(f"edge[{index}]: {exc}")
            continue
        relation = spec.relations.get(edge.relation)
        if relation is None:
            errors.append(f"edge[{index}]: undeclared relation {edge.relation}")
            continue
        if not edge.sources:
            errors.append(f"edge[{index}]: missing source provenance")
        for endpoint, expected in ((edge.source, relation.source), (edge.target, relation.target)):
            node = by_id.get(endpoint)
            if node is None:
                errors.append(f"edge[{index}]: missing endpoint {endpoint}")
            elif node.type in spec.entity_types and expected not in {
                node.type,
                *spec.ancestors(node.type),
            }:
                errors.append(f"edge[{index}]: endpoint {endpoint} is not a {expected}")
        parsed_edges.append(edge)
    for name, relation in spec.relations.items():
        pairs = {(edge.source, edge.target) for edge in parsed_edges if edge.relation == name}
        if "irreflexive" in relation.characteristics and any(a == b for a, b in pairs):
            errors.append(f"{name}: explicit irreflexive violation")
        if "asymmetric" in relation.characteristics and any((b, a) in pairs for a, b in pairs):
            errors.append(f"{name}: explicit asymmetric violation")
        if "functional" in relation.characteristics and len({a for a, _ in pairs}) < len(pairs):
            errors.append(f"{name}: explicit functional violation")
        if "inverse_functional" in relation.characteristics and len({b for _, b in pairs}) < len(
            pairs
        ):
            errors.append(f"{name}: explicit inverse-functional violation")
    return {
        "evidence_type": "graph_data_integrity",
        "valid": not errors,
        "status": "valid" if not errors else "invalid",
        "errors": errors,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "coverage": "Explicit records only; not OWL entailment or task correctness",
    }
