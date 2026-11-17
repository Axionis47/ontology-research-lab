"""Faulty fixture: selection ignores the required relationship."""


def select(selector, snapshot):
    return sorted(e["id"] for e in snapshot["entities"]
                  if e["type"] == selector["entity_type"]
                  and all(e["properties"].get(k) == v for k, v in selector["where"].items()))
