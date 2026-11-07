from types import SimpleNamespace

import pytest
from django.test import override_settings
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart

from apps.ai_chat.agent import (
    agent_model_string_for_transport,
    assert_can_run,
    build_main_agent,
    build_user_multimodal_prompt,
    conversation_to_model_messages,
    resolve_agent_model_name,
)
from apps.ai_chat.agent.policy import QuotaPolicyNotConfigured


@pytest.mark.parametrize(
    "transport,expected_prefix",
    [
        ("responses", "openai-responses:"),
        ("chat", "openai:"),
        ("", "openai:"),
    ],
)
def test_agent_model_string_for_transport(transport, expected_prefix):
    with override_settings(AI_OPENAI_TRANSPORT=transport):
        s = agent_model_string_for_transport("gpt-4o-mini")
        assert s == f"{expected_prefix}gpt-4o-mini"


def test_resolve_agent_model_name_explicit():
    with override_settings(OPENAI_CHAT_MODEL="x", OPENAI_MODEL="y"):
        assert resolve_agent_model_name("z") == "z"


def test_resolve_agent_model_name_prefers_chat_model():
    with override_settings(OPENAI_CHAT_MODEL="chat-model", OPENAI_MODEL="fallback-model"):
        assert resolve_agent_model_name(None) == "chat-model"


def test_resolve_agent_model_name_falls_back_to_openai_model():
    with override_settings(OPENAI_CHAT_MODEL="", OPENAI_MODEL="fallback-model"):
        assert resolve_agent_model_name(None) == "fallback-model"


def test_build_user_multimodal_prompt_text_and_binary():
    parts = build_user_multimodal_prompt("hi", [(b"\xff\xd8\xff", "image/jpeg")])
    assert parts[0] == "hi"
    assert parts[1].media_type == "image/jpeg"
    assert parts[1].data[:3] == b"\xff\xd8\xff"


def test_conversation_to_model_messages_skips_incomplete_assistant():
    rows = [
        SimpleNamespace(role="user", content="u1", is_draft=False),
        SimpleNamespace(role="assistant", content="half", is_incomplete=True),
        SimpleNamespace(role="assistant", content="done", is_incomplete=False),
    ]
    msgs = conversation_to_model_messages(rows)
    assert len(msgs) == 2
    assert isinstance(msgs[0], ModelRequest)
    assert isinstance(msgs[0].parts[0], UserPromptPart)
    assert isinstance(msgs[1], ModelResponse)


def test_assert_can_run_raises_when_quota_enforced():
    with override_settings(AI_CHAT_ENFORCE_QUOTA=True):
        with pytest.raises(QuotaPolicyNotConfigured):
            assert_can_run(1, "t", None, "gpt-4o-mini")


def test_build_main_agent_rejects_web_search_without_responses_transport():
    with override_settings(AI_OPENAI_TRANSPORT="chat"):
        with pytest.raises(ValueError, match="responses"):
            build_main_agent(include_builtin_web_search=True, defer_model_check=True)
