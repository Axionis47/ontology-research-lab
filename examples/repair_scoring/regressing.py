"""Deliberately bad candidate: fixes joins but drops single-result selections."""


def select(selector, snapshot):
    entities = {entity["id"]: entity for entity in snapshot["entities"]}
    related = selector["related"]
    rows = []
    for entity in entities.values():
        if entity["type"] != selector["entity_type"] or not all(
                entity["properties"].get(k) == v for k, v in selector["where"].items()):
            continue
        own, other = ("source", "target") if related["direction"] == "out" else ("target", "source")
        for edge in snapshot["relations"]:
            if edge[own] != entity["id"] or edge["type"] != related["relation_type"]:
                continue
            neighbor = entities[edge[other]]
            if neighbor["type"] == related["entity_type"] and all(
                    neighbor["properties"].get(k) == v for k, v in related["where"].items()):
                rows.append(entity["id"])
                break
    return [] if len(rows) == 1 else sorted(rows)
