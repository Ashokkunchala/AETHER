from jarvis.terminal.command_center import render_dashboard


def test_dashboard_contains_expected_sections():
    dashboard = render_dashboard()
    assert dashboard["header"] is not None
    assert dashboard["body"]["left"]["system"] is not None
    assert dashboard["body"]["core"] is not None
    assert dashboard["body"]["right"] is not None


def test_dashboard_renders_with_transcript_and_activity():
    dashboard = render_dashboard("Hello from test", "Unit test activity")
    assert dashboard["body"]["right"] is not None
