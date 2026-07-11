"""A fake OpenAI-compatible client for driving relay.py in tests.

`ScriptedClient(responder)` mimics `client.chat.completions.create(...)`.
`smart_responder` plays a minimal mentor + student: the mentor opens, then
gates each lesson (PASS on honest lessons, BLUFF_SUSPECTED on 3/6/9, read from
the injected lesson brief); the student recalls via practice_read then answers.
No network, no API key.
"""
import json
import re


class _Fn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.type = "function"
        self.function = _Fn(name, arguments)


class _Msg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, message):
        self.message = message


class _Resp:
    def __init__(self, message):
        self.choices = [_Choice(message)]


_ids = {"n": 0}


def say(text):
    return _Resp(_Msg(content=text))


def call_tool(name, **args):
    _ids["n"] += 1
    return _Resp(_Msg(tool_calls=[_ToolCall(f"tc{_ids['n']}", name, json.dumps(args))]))


def call_tools(*specs):
    """Response with multiple tool calls in one assistant message: call_tools(('ledger_write', {...}), ...)."""
    _ids["n"] += 1
    tcs = [_ToolCall(f"tc{_ids['n']}_{i}", name, json.dumps(args))
           for i, (name, args) in enumerate(specs)]
    return _Resp(_Msg(tool_calls=tcs))


def _assert_tool_calls_answered(messages):
    """Enforce OpenAI's rule: every assistant tool_call must have a matching tool response
    before the next request. Catches context corruption (e.g. a forced gate that leaves
    sibling tool calls unanswered) that a real endpoint would reject with a 400."""
    pending = []
    for m in messages:
        if m.get("role") == "assistant":
            pending += [tc["id"] for tc in (m.get("tool_calls") or [])]
        elif m.get("role") == "tool" and m.get("tool_call_id") in pending:
            pending.remove(m["tool_call_id"])
    if pending:
        raise AssertionError(f"unanswered tool_calls at request time: {pending}")


class _Completions:
    def __init__(self, outer):
        self._outer = outer

    def create(self, **kw):
        _assert_tool_calls_answered(kw["messages"])
        self._outer.calls.append(kw)
        return self._outer.responder(kw)


class _Chat:
    def __init__(self, outer):
        self.completions = _Completions(outer)


class ScriptedClient:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []
        self.chat = _Chat(self)


_BLUFF = {"3", "6", "9"}


def _current_lesson(messages):
    for m in reversed(messages):
        if m["role"] == "system":
            found = re.search(r"PRIVATE LESSON MATERIAL[^\d]*(\d+)", m["content"])
            if found:
                return found.group(1)
    return "?"


def smart_responder(kw):
    messages = kw["messages"]
    tools = kw.get("tools") or []
    names = {t["function"]["name"] for t in tools}
    choice = kw.get("tool_choice")
    forced_gate = isinstance(choice, dict) and choice.get("function", {}).get("name") == "advance_decision"
    role = messages[-1]["role"]

    if forced_gate:  # the relay is forcing the end-of-lesson verdict
        lesson = _current_lesson(messages)
        verdict = "BLUFF_SUSPECTED" if lesson in _BLUFF else "PASS"
        return call_tool("advance_decision", verdict=verdict, reason="forced-gate decision",
                         weak_spots=["needs more concrete practice detail"])

    is_mentor = "ledger_read" in names or "advance_decision" in names
    if is_mentor:  # opens, poses the transfer scenario, probes practice — always a question
        return say("[mentor] Walk me through exactly what you did and what went wrong.")

    # student
    if role == "tool":  # just saw the practice_read result -> answer
        return say("[student] Okay, here's my answer.")
    return call_tool("practice_read")
