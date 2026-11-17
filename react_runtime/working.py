"""Durable derived working index, bounded views, and observable progress."""

from collections import defaultdict
import hashlib
import json


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def evidence_signature(value):
    if isinstance(value, dict) and (value.get("rejected") or value.get("mcp_result", {}).get("isError")):
        value = {"error": value.get("message", value.get("mcp_result"))}
    def semantic(v):
        if isinstance(v, dict): return {k: semantic(x) for k, x in v.items() if k not in {"catalog_revision", "revision", "offset", "next_offset", "query", "request_id", "output_id", "step", "source_output_id"}}
        if isinstance(v, list): return [semantic(x) for x in v]
        return v
    return signature(semantic(value))


class WorkingState:
    def __init__(self, store):
        self.store = store
        store.db.execute("CREATE TABLE IF NOT EXISTS working(kind TEXT,key TEXT,value TEXT,source TEXT,step INTEGER,PRIMARY KEY(kind,key))")
        self.identities = defaultdict(set)
        self.failures = defaultdict(int)
        self.seen = set()
        self.stagnant = 0
        self.recovery_pending = None

    def put(self, kind, key, value, source, step):
        with self.store.db:
            self.store.db.execute("INSERT OR REPLACE INTO working VALUES (?,?,?,?,?)", (kind, str(key), json.dumps(value), source, step))

    def page(self, kind=None, offset=0, limit=10):
        if kind not in {None, "tools", "schemas", "entities", "relations", "state", "evidence", "effects", "pending", "bindings", "pages"}:
            raise ValueError("Unknown working-state kind")
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Invalid working-state page")
        rows = self.store.db.execute("SELECT * FROM working WHERE (? IS NULL OR kind=?) ORDER BY kind,key LIMIT ? OFFSET ?", (kind, kind, limit + 1, offset)).fetchall()
        records = [{"kind": r[0], "key": r[1], "value": json.loads(r[2]), "source_output_id": r[3], "step": r[4]} for r in rows[:limit]]
        for record in records:
            if record["kind"] != "entities": continue
            identity = record["value"]["id"]
            related = self.store.db.execute("SELECT value,source FROM working WHERE kind='relations' AND (json_extract(value,'$.source')=? OR json_extract(value,'$.target')=?) ORDER BY key LIMIT 21", (identity, identity)).fetchall()
            record["value"]["relations"] = [json.loads(r[0]) for r in related[:20]]
            record["relations_truncated"] = len(related) > 20
        return {"records": records, "next_offset": offset + limit if len(rows) > limit else None}

    def view(self, fields=None):
        # Full records are retrieved via read_working/read_output. This view
        # remains bounded independently of episode length and graph size.
        counts = dict(self.store.db.execute("SELECT kind,count(*) FROM working GROUP BY kind"))
        recent = self.store.db.execute("SELECT kind,key,source FROM working WHERE kind IN ('pending','effects','bindings') ORDER BY step DESC,kind,key LIMIT 4").fetchall()
        view = {"counts": counts, "recent": [{"kind": r[0], "key": r[1][:160], "output_id": r[2]} for r in recent],
                "retrieve": "read_working", "consecutive_no_progress": self.stagnant}
        state = self.store.db.execute("SELECT value,source FROM working WHERE kind='state' ORDER BY step DESC LIMIT 1").fetchone()
        if state:
            value = json.loads(state[0])
            view["state_revision"] = {"scope": value["scope"][:200], "revision": value["revision"] if len(value["revision"]) <= 200 else None,
                                      "retrieve_full_state": len(value["revision"]) > 200, "source_output_id": state[1]}
        pending = self.store.db.execute("SELECT key,value FROM working WHERE kind='pending' ORDER BY step DESC LIMIT 2").fetchall()
        if pending:
            view["pending_corrections"] = [{"tool": r[0], "messages": [m[:500] for m in json.loads(r[1])["corrections"]],
                                            "attempts_remaining": max(0, 3 - json.loads(r[1])["failures"])} for r in pending]
        if fields is not None:
            if "revision" not in fields: view.pop("state_revision", None)
            if "pending" not in fields: view.pop("pending_corrections", None)
            view["recent"] = [r for r in view["recent"] if r["kind"] in fields]
        return view

    def _facts(self, value, source, step):
        if isinstance(value, list):
            for item in value: self._facts(item, source, step)
        elif isinstance(value, dict):
            if isinstance(value.get("scope"), str) and isinstance(value.get("revision"), str):
                self.put("state", value["scope"], {"scope": value["scope"], "revision": value["revision"]}, source, step)
                if value.get("complete") is True and "relations" in value:
                    with self.store.db: self.store.db.execute("DELETE FROM working WHERE kind='relations'")
            for edge in value.get("relations", []) if isinstance(value.get("relations"), list) else []:
                if isinstance(edge, dict) and all(isinstance(edge.get(k), str) for k in ("source", "type", "target")):
                    self.put("relations", signature(edge), edge, source, step)
            if "id" in value and "type" in value and "properties" in value:
                identity = value["id"]
                self.identities["entity_ids"].add(identity)
                self.put("entities", identity, value, source, step)
                # Typed adapter IDs are prefix:native_id; retain the explicit
                # native identity binding, not any model-invented number.
                if isinstance(identity, str) and ":" in identity:
                    prefix, native = identity.rsplit(":", 1)
                    if native.isdigit() and prefix.casefold() == value["type"].casefold():
                        field = prefix.casefold() + "_id"
                        self.identities[field].add(int(native))
                        self.put("bindings", field + ":" + native, {"field": field, "value": int(native), "entity_id": identity}, source, step)
            for key, child in value.items():
                if key.endswith("_id") and type(child) in {str, int}:
                    self.identities[key].add(child)
                    self.put("bindings", key + ":" + str(child), {"field": key, "value": child}, source, step)
                if isinstance(child, (dict, list)): self._facts(child, source, step)

    def observe(self, action, arguments, value, source, step, *, effect=False):
        novel = False
        if not isinstance(value, dict): value = {"value": value}
        if value.get("rejected") or value.get("mcp_result", {}).get("isError"):
            value = {"error": value.get("message", value.get("mcp_result"))}
        else:
            if action not in {"read_working", "read_output", "list_outputs"}: self._facts(value, source, step)
            revision = value.get("catalog_revision")
            if isinstance(value.get("tools"), list):
                for tool in value["tools"]:
                    self.put("tools", str(revision) + ":" + tool["name"], tool, source, step)
            if isinstance(value.get("tool"), dict):
                self.put("schemas", value["tool"]["name"], value["tool"], source, step)
            if "next_offset" in value:
                self.put("pages", signature([action, {k: v for k, v in arguments.items() if k != "offset"}]),
                         {"arguments": arguments, "next_offset": value["next_offset"]}, source, step)
            if effect: self.put("effects", signature([action, arguments]), {"action": action, "arguments": arguments, "status": "returned_requires_readback"}, source, step)
        # Ignore transport IDs and requested offsets. An empty page at a new
        # offset is not new evidence. Nonempty pages/new schemas still count.
        key = evidence_signature(value)
        novel = key not in self.seen
        self.seen.add(key)
        self.stagnant = 0 if novel else self.stagnant + 1
        self.put("evidence", source, {"action": action, "arguments": arguments, "novel": novel}, source, step)
        return novel

    def binding_error(self, name, arguments, *, mutation):
        if not mutation: return None
        for key, value in arguments.items():
            if key == "entity_ids":
                if isinstance(value, list) and any(v not in self.identities[key] for v in value):
                    return "entity_ids must reference records observed in this episode"
            elif key.endswith("_id") and (type(value) not in {int, str} or value not in self.identities[key]):
                return f"{key} must be grounded in an observed {key}; read evidence before rebinding"
        return None

    def reject(self, tool, message, source, step):
        self.failures[tool] += 1
        prior = self.store.db.execute("SELECT value FROM working WHERE kind='pending' AND key=?", (tool,)).fetchone()
        corrections = (json.loads(prior[0])["corrections"] if prior else []) + [message]
        self.put("pending", tool, {"message": message, "corrections": corrections[-3:], "failures": self.failures[tool]}, source, step)
        # First rejection plus no more than two repair attempts.
        return self.failures[tool] > 2

    def resolve(self, tool):
        self.failures[tool] = 0
        with self.store.db: self.store.db.execute("DELETE FROM working WHERE kind='pending' AND key=?", (tool,))
