from copy import deepcopy
import json
import unittest
import io
from unittest.mock import patch
from jsonschema import Draft202012Validator, ValidationError

from react_runtime.ollama import payload, proposal_schema, actor_proposal
from appworld_runtime.batch import actor_instructions


class OllamaTransportTests(unittest.TestCase):
    def test_actual_unicode_provider_request_uses_measured_serialization(self):
        from react_runtime.ollama import main
        config = {"model": "configured", "think": False, "num_ctx": 8192, "num_predict": 512, "temperature": 0, "base_url": "http://localhost", "timeout_seconds": 10}
        context = {"task": {"objective": "é" * 1000}, "turn": {"request_id": "id"}, "tools": [], "context_limit_chars": 4000}
        sent = []
        def request(url, timeout):
            if isinstance(url, str): result = {"models": [{"name": "configured", "context_length": 8192}]}
            else:
                sent.append(url.data.decode())
                self.assertLessEqual(len(sent[-1]), context["context_limit_chars"])
                result = {"model": "configured", "done": True, "message": {"content": "done"}}
            return io.BytesIO(json.dumps(result).encode())
        with patch("react_runtime.ollama.configuration", return_value=config), patch("urllib.request.urlopen", side_effect=request), patch("sys.stdin", io.StringIO(json.dumps(context))), patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            self.assertEqual(main(), 0)
        self.assertIn("é", sent[0])

    def test_native_tool_receipts_and_inspected_api_mapping_are_structural(self):
        context = {"task": {"objective": "keep this goal"}, "turn": {"request_id": "current"},
            "system_instructions": actor_instructions({"supervisor": {}, "task_datetime": "today", "application": "test"}),
            "tools": [{"name": "call_tool", "description": "broker", "arguments": {"type": "object"}}],
            "inspected_tools": [{"name": "app__update", "description": "update", "inputSchema": {"type": "object", "properties": {"id": {"type": "integer"}}}}],
            "recent_steps": [{"action_key": json.dumps(["call_tool", {"name": "app__update", "arguments": {"id": 7}}]),
                              "observation": {"code": "OK", "preview": '{"updated":true}', "output_id": "saved"}}]}
        config = {"model": "configured", "think": False, "num_ctx": 8192, "num_predict": 512, "temperature": 0}
        actual = payload(context, config)
        self.assertNotIn("format", actual)
        self.assertNotIn("action_id", actual["messages"][0]["content"])
        self.assertIn("Supply only their declared parameters", actual["messages"][0]["content"])
        self.assertEqual(actual["messages"][-1]["role"], "tool")
        self.assertEqual(actual["messages"][-1]["tool_name"], "app__update")
        self.assertEqual(json.loads(actual["messages"][-1]["content"])["result"], {"updated": True})
        self.assertIn("app__update", [d["function"]["name"] for d in actual["tools"]])
        result = actor_proposal(context, {"tool_calls": [{"function": {"name": "app__update", "arguments": {"id": 8}}}, {"function": {"name": "finish", "arguments": {"answer": "not dispatched"}}}]})
        self.assertEqual(result["request_id"], "current")
        self.assertEqual(result["action_id"], "call_tool")
        self.assertEqual(result["arguments"], {"name": "app__update", "arguments": {"id": 8}})

    def test_applies_config_and_preserves_original_goal_and_full_context(self):
        context = {"system_instructions": "protocol", "task": {"objective": "original goal", "constraints": []},
                   "recent_steps": [{"observation": "evidence"}], "turn": {"request_id": "id"}}
        original = deepcopy(context)
        config = {"model": "configured", "think": False, "num_ctx": 8192, "num_predict": 512, "temperature": 0}
        result = payload(context, config)
        self.assertEqual(result["options"], {"num_ctx": 8192, "num_predict": 512, "temperature": 0})
        self.assertFalse(result["stream"])
        self.assertFalse(result["think"])
        self.assertEqual(result["messages"][0], {"role": "system", "content": "protocol"})
        actual = json.loads(result["messages"][1]["content"])
        self.assertEqual(actual["task"]["objective"], "original goal")
        self.assertEqual(actual["recent_steps"], context["recent_steps"])
        self.assertEqual(context, original)
        self.assertNotIn("tools", result)

    def test_native_call_generation_is_bound_to_inspected_schema(self):
        context = {"turn": {"request_id": "current"}, "tools": [{"name": "call_tool", "arguments": {}}],
            "inspected_tools": [{"name": "app__update", "inputSchema": {"type": "object", "properties": {"record_id": {"type": "integer"}}, "required": ["record_id"]}}]}
        validator = Draft202012Validator(proposal_schema(context))
        proposal = {"kind": "act", "request_id": "current", "action_id": "call_tool", "arguments": {"name": "app__update", "arguments": {"record_id": 7}}, "evidence_ids": [], "reason": "Update observed record"}
        validator.validate(proposal)
        for arguments in ({"record_ids": [7]}, {"record_id": "entity:7"}, {"record_id": 7, "override": True}):
            proposal["arguments"]["arguments"] = arguments
            with self.assertRaises(ValidationError): validator.validate(proposal)
        context["inspected_tools"] = []
        proposal["arguments"]["arguments"] = {"record_id": 7}
        with self.assertRaises(ValidationError): Draft202012Validator(proposal_schema(context)).validate(proposal)


if __name__ == "__main__": unittest.main()
