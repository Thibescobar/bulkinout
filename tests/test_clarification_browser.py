import json
import stat
import urllib.parse
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from bulkinout.clarification_browser import (
    BrowserClarification,
    _ClarificationHandler,
    _Session,
    _parse_submission,
    _render_form,
    collect_clinician_answers,
    next_interactive_answer_path,
    write_interactive_answers,
)
from bulkinout.core.models import AnswerFile, AnswerItem, MissingQuestion
from bulkinout.errors import ConfigurationError


def question(field="imaging_safety.pregnancy", *, kind="boolean", text="Grossesse ?"):
    return MissingQuestion(
        question_id="question",
        field=field,
        question=text,
        importance="critical",
        reason="Technical reason.",
        required_to_choose=True,
        blocking=True,
        answer_kind=kind,
        clinical_reason="Cette réponse modifie la stratégie.",
    )


def test_browser_form_is_french_typed_self_contained_and_escapes_questions():
    session = _Session(
        token="token",
        questions=[question(text="Grossesse <script>alert(1)</script> ?")],
    )

    html = _render_form(session)

    assert '<html lang="fr">' in html
    assert '<option value="true">Oui</option>' in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert 'action="/token/submit"' in html
    assert "https://" not in html
    assert "http://" not in html


def test_browser_form_renders_numeric_and_text_controls_with_french_fallback_reasons():
    blocking_number = question("labs.value", kind="number", text="Valeur ?")
    blocking_number.clinical_reason = None
    required_text = question("current_problem.detail", kind="text", text="Détail ?")
    required_text.clinical_reason = None
    required_text.blocking = False

    html = _render_form(_Session(token="token", questions=[blocking_number, required_text]))

    assert 'type="number" step="any"' in html
    assert 'type="text"' in html
    assert "indispensable à la sécurité" in html
    assert "peut modifier le choix" in html


def test_submission_preserves_boolean_integer_number_and_text_types():
    questions = [
        question(),
        question("current_problem.gcs", kind="integer", text="Glasgow ?"),
        question("labs.egfr_ml_min_1_73m2", kind="number", text="DFG ?"),
        question("current_problem.onset", kind="text", text="Début ?"),
    ]
    session = _Session(token="token", questions=questions)
    body = urllib.parse.urlencode(
        {
            "role": "emergency_clinician",
            "action": "continue",
            "answer_0": "false",
            "answer_1": "15",
            "answer_2": "82,5",
            "answer_3": "08:30",
        }
    ).encode()

    outcome = _parse_submission(body, session)

    assert [item.value for item in outcome.answer_file.answers] == [False, 15, 82.5, "08:30"]
    assert all(item.responder_role == "emergency_clinician" for item in outcome.answer_file.answers)
    assert all(
        item.response_method == "interactive_browser" for item in outcome.answer_file.answers
    )
    assert outcome.answer_file.answers[0].answered_at is not None
    assert outcome.answer_file.interaction_action == "continue"
    assert outcome.escalated is False


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "clinician", "action": "continue"},
        {"role": "unknown", "action": "continue", "answer_0": "true"},
        {"role": "clinician", "action": "continue", "answer_0": "not-a-boolean"},
    ],
)
def test_submission_rejects_missing_unknown_and_invalid_typed_values(payload):
    session = _Session(token="token", questions=[question()])

    with pytest.raises(ValueError):
        _parse_submission(urllib.parse.urlencode(payload).encode(), session)


def test_submission_rejects_invalid_utf8():
    with pytest.raises(ValueError, match="invalid form"):
        _parse_submission(b"\xff", _Session(token="token", questions=[question()]))


def test_submission_records_unavailable_answers_and_explicit_escalation():
    session = _Session(token="token", questions=[question()])
    body = urllib.parse.urlencode(
        {"role": "clinician", "action": "escalate", "answer_0": ""}
    ).encode()

    outcome = _parse_submission(body, session)

    assert outcome.escalated is True
    assert outcome.answer_file.answers[0].value is None
    assert outcome.answer_file.interaction_action == "escalate"


def _memory_handler(session, *, path, headers, body=b""):
    handler = object.__new__(_ClarificationHandler)
    handler.server = SimpleNamespace(clarification_session=session)
    handler.path = path
    handler.headers = headers
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()
    handler.statuses = []
    handler.response_headers = {}
    handler.send_response = lambda status: handler.statuses.append(status)
    handler.send_header = lambda name, value: handler.response_headers.__setitem__(name, value)
    handler.end_headers = lambda: None
    return handler


def test_http_handler_serves_form_with_security_headers_and_accepts_one_submission():
    session = _Session(token="secret", questions=[question()], port=43125)
    get_handler = _memory_handler(
        session,
        path="/secret",
        headers={"Host": "127.0.0.1:43125"},
    )

    get_handler.do_GET()

    assert get_handler.statuses == [200]
    assert get_handler.response_headers["Cache-Control"] == "no-store"
    assert get_handler.response_headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in get_handler.response_headers["Content-Security-Policy"]
    assert "Clarification clinique" in get_handler.wfile.getvalue().decode()

    body = urllib.parse.urlencode(
        {"role": "clinician", "action": "continue", "answer_0": "false"}
    ).encode()
    post_handler = _memory_handler(
        session,
        path="/secret/submit",
        headers={
            "Host": "127.0.0.1:43125",
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(body)),
        },
        body=body,
    )

    post_handler.do_POST()

    assert post_handler.statuses == [200]
    assert session.outcome is not None
    assert session.outcome.answer_file.answers[0].value is False
    post_handler.log_message("ignored", "value")


@pytest.mark.parametrize(
    ("path", "host"),
    [("/wrong", "127.0.0.1:43125"), ("/secret", "malicious.example")],
)
def test_http_handler_rejects_wrong_token_or_host(path, host):
    session = _Session(token="secret", questions=[question()], port=43125)
    handler = _memory_handler(session, path=path, headers={"Host": host})

    handler.do_GET()

    assert handler.statuses == [404]


@pytest.mark.parametrize(
    ("headers", "body", "status"),
    [
        ({"Host": "127.0.0.1:43125"}, b"", 400),
        (
            {
                "Host": "127.0.0.1:43125",
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": "invalid",
            },
            b"",
            400,
        ),
        (
            {
                "Host": "127.0.0.1:43125",
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": str(65 * 1024),
            },
            b"",
            413,
        ),
        (
            {
                "Host": "127.0.0.1:43125",
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": "3",
            },
            b"bad",
            400,
        ),
    ],
)
def test_http_handler_rejects_invalid_post_requests(headers, body, status):
    session = _Session(token="secret", questions=[question()], port=43125)
    handler = _memory_handler(
        session,
        path="/secret/submit",
        headers=headers,
        body=body,
    )

    handler.do_POST()

    assert handler.statuses == [status]
    assert session.outcome is None


def test_http_handler_rejects_replayed_submission():
    session = _Session(
        token="secret",
        questions=[question()],
        port=43125,
        outcome=BrowserClarification(AnswerFile()),
    )
    handler = _memory_handler(
        session,
        path="/secret/submit",
        headers={"Host": "127.0.0.1:43125"},
    )

    handler.do_POST()

    assert handler.statuses == [404]


def test_collect_answers_uses_loopback_random_port_and_closes_server():
    opened = []

    class FakeServer:
        def __init__(self, address, handler):
            assert address == ("127.0.0.1", 0)
            assert handler is _ClarificationHandler
            self.server_address = ("127.0.0.1", 43125)
            self.timeout = None
            self.closed = False

        def handle_request(self):
            self.clarification_session.outcome = BrowserClarification(
                AnswerFile(answers=[AnswerItem(field="imaging_safety.pregnancy", value=True)])
            )

        def server_close(self):
            self.closed = True

    server = None

    def server_factory(address, handler):
        nonlocal server
        server = FakeServer(address, handler)
        return server

    outcome = collect_clinician_answers(
        [question()],
        timeout_seconds=2,
        opener=lambda url: opened.append(url) or True,
        server_factory=server_factory,
    )

    assert server is not None
    assert outcome is not None
    assert outcome.answer_file.answers[0].value is True
    assert opened[0].startswith("http://127.0.0.1:43125/")
    assert server.closed is True


class _IdleServer:
    server_address = ("127.0.0.1", 43125)
    timeout = None

    def __init__(self):
        self.closed = False

    def handle_request(self):
        raise AssertionError("No request should be handled")

    def server_close(self):
        self.closed = True


def test_collect_answers_does_not_wait_when_browser_cannot_open():
    server = _IdleServer()
    assert (
        collect_clinician_answers(
            [question()], opener=lambda url: False, server_factory=lambda *args: server
        )
        is None
    )
    assert server.closed is True
    assert collect_clinician_answers([], opener=lambda url: True) is None


def test_collect_answers_handles_browser_errors_and_timeout():
    def fail(_url):
        raise RuntimeError("no browser")

    assert (
        collect_clinician_answers(
            [question()], opener=fail, server_factory=lambda *args: _IdleServer()
        )
        is None
    )
    assert (
        collect_clinician_answers(
            [question()],
            timeout_seconds=0,
            opener=lambda url: True,
            server_factory=lambda *args: _IdleServer(),
        )
        is None
    )


def test_interactive_answer_files_are_private_and_never_overwritten(tmp_path):
    answer_file = AnswerFile(answers=[AnswerItem(field="imaging_safety.pregnancy", value=False)])
    path = next_interactive_answer_path(tmp_path)

    write_interactive_answers(path, answer_file)

    assert path.name == "answers.interactive.1.json"
    assert json.loads(path.read_text())["answers"][0]["value"] is False
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert next_interactive_answer_path(tmp_path).name == "answers.interactive.2.json"
    with pytest.raises(ConfigurationError, match="already exists"):
        write_interactive_answers(path, answer_file)


def test_interactive_answer_path_fails_when_all_slots_are_taken(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "exists", lambda self: True)

    with pytest.raises(ConfigurationError, match="No available interactive answer filename"):
        next_interactive_answer_path(tmp_path)
