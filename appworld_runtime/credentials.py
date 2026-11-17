"""Session-owned authentication bindings, separate from model-chosen arguments."""

from copy import deepcopy


class SessionCredentials:
    def __init__(self, application, catalog):
        self.application, self.catalog = application, catalog
        self.values = {}

    def bind(self, application, values):
        if application != self.application or set(values) != {"access_token"}:
            raise ValueError("Only this application's session access_token may be bound")
        if not isinstance(values["access_token"], str) or not values["access_token"]:
            raise ValueError("A nonempty session access token is required")
        if self.values: raise ValueError("Session authentication is already bound")
        self.values = dict(values)
        return {"application": application, "managed_fields": sorted(values)}

    def fields(self, name):
        tool = self.catalog.describe(name)["tool"]
        if name.split("__", 1)[0] != self.application: return {}
        return {k: v for k, v in self.values.items() if k in tool["inputSchema"].get("properties", {})}

    def describe(self, name):
        result = deepcopy(self.catalog.describe(name))
        fields = self.fields(name)
        if fields:
            schema = result["tool"]["inputSchema"]
            for key in fields: schema["properties"].pop(key)
            schema["required"] = [k for k in schema.get("required", []) if k not in fields]
            result["managed_session_fields"] = sorted(fields)
            result["tool"]["description"] = result["tool"].get("description", "") + " Session authentication is supplied by the broker. Omit access_token."
        return result

    def prepare(self, name, arguments):
        fields = self.fields(name)
        if any(k in arguments and arguments[k] != v for k, v in fields.items()):
            raise ValueError("Omit access_token: this session supplies its application credential automatically")
        return {**arguments, **fields}, sorted(fields)
