from copy import deepcopy
import unittest

from appworld_runtime.catalog import Catalog
from appworld_runtime.credentials import SessionCredentials


class SessionCredentialTests(unittest.TestCase):
    def setUp(self):
        schema = {"type": "object", "properties": {"access_token": {"type": "string"}, "artist_id": {"type": "integer"}},
                  "required": ["access_token", "artist_id"]}
        self.catalog = Catalog([{"name": name, "description": "Example", "inputSchema": deepcopy(schema)}
                                for name in ("spotify__follow_artist", "supervisor__example")], "spotify")
        self.credentials = SessionCredentials("spotify", self.catalog)

    def test_broker_injects_credentials_and_preserves_native_validation(self):
        self.credentials.bind("spotify", {"access_token": "secret"})
        arguments, fields = self.credentials.prepare("spotify__follow_artist", {"artist_id": 7})
        self.assertEqual(arguments, {"artist_id": 7, "access_token": "secret"})
        self.assertEqual(fields, ["access_token"])
        self.catalog.validate_call("spotify__follow_artist", arguments)
        with self.assertRaises(Exception): self.catalog.validate_call("spotify__follow_artist", {**arguments, "remote_override": True})

    def test_bound_credentials_are_removed_from_actor_schema_not_native_schema(self):
        self.credentials.bind("spotify", {"access_token": "secret"})
        described = self.credentials.describe("spotify__follow_artist")
        schema = described["tool"]["inputSchema"]
        self.assertNotIn("access_token", schema["properties"])
        self.assertEqual(schema["required"], ["artist_id"])
        self.assertNotIn("secret", str(described))
        self.assertIn("access_token", self.catalog.describe("spotify__follow_artist")["tool"]["inputSchema"]["required"])

    def test_credentials_cannot_cross_app_scope_or_change_business_arguments(self):
        for application, values in (("supervisor", {"access_token": "secret"}), ("spotify", {"artist_id": "7"})):
            with self.assertRaises(ValueError): self.credentials.bind(application, values)
        self.credentials.bind("spotify", {"access_token": "secret"})
        self.assertEqual(self.credentials.prepare("supervisor__example", {"artist_id": 7}), ({"artist_id": 7}, []))
        with self.assertRaises(ValueError): self.credentials.prepare("spotify__follow_artist", {"artist_id": 7, "access_token": "invented"})
        with self.assertRaises(ValueError): self.credentials.bind("spotify", {"access_token": "replacement"})


if __name__ == "__main__": unittest.main()
