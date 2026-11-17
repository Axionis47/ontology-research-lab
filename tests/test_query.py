import unittest

from react_runtime.query import query_snapshot, query_schema
from jsonschema import Draft202012Validator, ValidationError
from repair_runtime.program import Unsupported
from scripts.demo_repair_scoring import cases


class ObservationQueryTests(unittest.TestCase):
    def test_empty_arguments_inspect_schema_without_selecting_task_targets(self):
        snapshot = cases()[0][2]["before"]
        result = query_snapshot(snapshot, {})
        self.assertEqual(result["types"]["Ticket"]["count"], 4)
        self.assertNotIn("entities", result)
        self.assertNotIn("selector", result)

    def test_caller_predicates_and_pagination_drive_the_result(self):
        snapshot = cases()[0][2]["before"]
        for i, entity in enumerate(snapshot["entities"]): entity["properties"]["quantity"] = i
        arguments = {"entity_type": "Ticket", "where": {"status": "open"}, "numeric": [{"property": "quantity", "op": "gte", "value": 3}], "limit": 1}
        first = query_snapshot(snapshot, arguments)
        self.assertEqual(first["total_matches"], 2)
        self.assertEqual([e["id"] for e in first["entities"]], ["ticket:2"])
        second = query_snapshot(snapshot, {**arguments, "offset": first["next_offset"]})
        self.assertEqual([e["id"] for e in second["entities"]], ["ticket:3"])
        self.assertIsNone(second["next_offset"])
        # Querying east/open is allowed even though this task requests west.
        self.assertEqual(first["relations"][0]["source"], "ticket:2")

    def test_unknown_property_is_not_silently_false(self):
        with self.assertRaises(ValidationError): query_snapshot(cases()[0][2]["before"], {"entity_type": "Ticket", "where": {"unobserved": True}})

    def test_query_schema_rejects_invented_type_and_comparison_in_equality_field(self):
        validator = Draft202012Validator(query_schema(cases()[0][2]["before"]))
        validator.validate({"entity_type": "Ticket", "where": {"status": "open"}})
        for arguments in ({"entity_type": "ticket"}, {"entity_type": "Ticket", "where": {"status": {"op": "gte", "value": 22}}}):
            with self.assertRaises(ValidationError): validator.validate(arguments)


if __name__ == "__main__": unittest.main()
