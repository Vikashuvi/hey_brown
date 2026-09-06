from core.intent import DeterministicIntentRouter


def test_intent_router_open_apps():
    router = DeterministicIntentRouter()

    # Open local app
    r1 = router.route("open Safari")
    assert r1.action_type == "tool_call"
    assert r1.tool_name == "open_application"
    assert r1.tool_args["app_name"] == "Safari"
    assert r1.tool_args["device"] == "paperball"

    # Open app on Error Boy
    r2 = router.route("open VS Code on Error Boy")
    assert r2.action_type == "tool_call"
    assert r2.tool_name == "open_application"
    assert r2.tool_args["app_name"] == "Visual Studio Code"
    assert r2.tool_args["device"] == "error_boy"


def test_intent_router_open_urls():
    router = DeterministicIntentRouter()

    # Known site
    r1 = router.route("open youtube")
    assert r1.action_type == "tool_call"
    assert r1.tool_name == "open_url"
    assert r1.tool_args["url"] == "https://www.youtube.com"

    # Custom domain
    r2 = router.route("open github.com on Error Boy")
    assert r2.action_type == "tool_call"
    assert r2.tool_name == "open_url"
    assert r2.tool_args["device"] == "error_boy"


def test_intent_router_status_and_stops():
    router = DeterministicIntentRouter()

    # Status
    r1 = router.route("how is Paperball doing?")
    assert r1.action_type == "tool_call"
    assert r1.tool_name == "get_system_status"
    assert r1.tool_args["device"] == "paperball"

    # Stop / interruption
    r2 = router.route("actually stop")
    assert r2.action_type == "stop"

    r3 = router.route("quiet!")
    assert r3.action_type == "stop"


def test_intent_router_conversation():
    router = DeterministicIntentRouter()

    r1 = router.route("hey brown")
    assert r1.action_type == "conversation"
    assert "here" in r1.direct_response.lower()

    r2 = router.route("who are you?")
    assert r2.action_type == "conversation"
    assert "Brown" in r2.direct_response
