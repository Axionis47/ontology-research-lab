"""Engineer-authored repair: resolve the related entity before accepting a row."""


def select(selector, snapshot):
    entities = {entity["id"]: entity for entity in snapshot["entities"]}

    def matches(entity, spec):
        return entity["type"] == spec["entity_type"] and all(
            k in entity["properties"] and entity["properties"][k] == v for k, v in spec["where"].items())

    selected = []
    for entity in entities.values():
        if not matches(entity, selector):
            continue
        if "related" in selector:
            related = selector["related"]
            own, other = ("source", "target") if related["direction"] == "out" else ("target", "source")
            neighbors = [edge[other] for edge in snapshot["relations"]
                         if edge["type"] == related["relation_type"] and edge[own] == entity["id"]]
            if not any(key in entities and matches(entities[key], related) for key in neighbors):
                continue
        selected.append(entity["id"])
    return sorted(selected)
