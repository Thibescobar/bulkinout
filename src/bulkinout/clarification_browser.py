"""Short-lived loopback browser form for optional clinician clarification."""

from __future__ import annotations

import json
import os
import secrets
import time
import webbrowser
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable, Literal, cast
from urllib.parse import parse_qs

from .core.models import AnswerFile, AnswerItem, MissingQuestion
from .errors import ConfigurationError
from .types import JsonValue

_MAX_BODY_BYTES = 64 * 1024
_DEFAULT_TIMEOUT_SECONDS = 600.0
_SECURITY_POLICY = (
    "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)


@dataclass(slots=True)
class BrowserClarification:
    answer_file: AnswerFile
    escalated: bool = False


@dataclass(slots=True)
class _Session:
    token: str
    questions: list[MissingQuestion]
    port: int = 0
    outcome: BrowserClarification | None = None


def _clinical_reason(question: MissingQuestion) -> str:
    if question.clinical_reason:
        return question.clinical_reason
    if question.blocking:
        return "Cette information est indispensable à la sécurité de la proposition."
    return "Cette information peut modifier le choix de l'examen ou de son protocole."


def _answer_control(index: int, question: MissingQuestion) -> str:
    name = f"answer_{index}"
    if question.answer_kind == "boolean":
        return (
            f'<select name="{name}"><option value="">Information indisponible</option>'
            '<option value="true">Oui</option><option value="false">Non</option></select>'
        )
    input_type = "number" if question.answer_kind in {"integer", "number"} else "text"
    step = ' step="1"' if question.answer_kind == "integer" else ' step="any"'
    if input_type == "text":
        step = ""
    return (
        f'<input name="{name}" type="{input_type}"{step} '
        'placeholder="Information indisponible si laissé vide">'
    )


def _render_form(session: _Session) -> str:
    question_cards = []
    for index, question in enumerate(session.questions):
        importance = "Information bloquante" if question.blocking else "Information requise"
        question_cards.append(
            "<fieldset><legend>"
            f"{index + 1}. {escape(question.question)}</legend>"
            f'<p class="reason">{escape(_clinical_reason(question))}</p>'
            f'<p class="tag">{importance}</p>{_answer_control(index, question)}</fieldset>'
        )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta name="referrer" content="no-referrer"><title>Clarification clinique — Bulkinout</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;color:#173042;background:#f4f8f9;margin:0}}
main{{max-width:760px;margin:32px auto;background:#fff;padding:32px;border-radius:14px}}
h1{{color:#075b66}}fieldset{{border:1px solid #cadcdf;border-radius:10px;margin:22px 0;padding:18px}}
legend{{font-weight:700;padding:0 8px}}select,input{{box-sizing:border-box;width:100%;padding:11px}}
.reason{{color:#405b66}}.tag{{font-size:.85rem;color:#98520a}}.warning{{border-left:4px solid #ef7d32;padding:10px;background:#fff8f1}}
.actions{{display:flex;gap:12px;flex-wrap:wrap}}button{{border:0;border-radius:7px;padding:12px 16px;font-weight:700}}
.continue{{background:#087f8c;color:#fff}}.escalate{{background:#fff0e5;color:#8a420c}}
</style></head><body><main><h1>Clarification clinique</h1>
<p>Bulkinout a besoin des informations suivantes avant de recalculer sa proposition.</p>
<p class="warning">Les réponses seront tracées mais ne constituent ni une authentification ni une signature clinique.</p>
<form method="post" action="/{session.token}/submit">
<label for="role">Rôle du répondant</label><select id="role" name="role">
<option value="clinician">Clinicien prescripteur</option>
<option value="emergency_clinician">Médecin urgentiste</option></select>
{"".join(question_cards)}
<div class="actions"><button class="continue" name="action" value="continue">Recalculer la proposition</button>
<button class="escalate" name="action" value="escalate">Information indisponible — appeler le téléradiologue</button></div>
</form></main></body></html>"""


def _parse_answer(raw: str, question: MissingQuestion) -> JsonValue:
    value = raw.strip()
    if not value:
        return None
    if question.answer_kind == "boolean":
        if value not in {"true", "false"}:
            raise ValueError("invalid boolean")
        return value == "true"
    if question.answer_kind == "integer":
        return int(value)
    if question.answer_kind == "number":
        return float(value.replace(",", "."))
    return value


def _parse_submission(body: bytes, session: _Session) -> BrowserClarification:
    try:
        form = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("invalid form") from error
    expected = {"role", "action"} | {f"answer_{index}" for index in range(len(session.questions))}
    if set(form) != expected or any(len(values) != 1 for values in form.values()):
        raise ValueError("unexpected form fields")
    raw_role = form["role"][0]
    raw_action = form["action"][0]
    if raw_role not in {"clinician", "emergency_clinician"} or raw_action not in {
        "continue",
        "escalate",
    }:
        raise ValueError("invalid form value")
    role = cast(Literal["clinician", "emergency_clinician"], raw_role)
    action = cast(Literal["continue", "escalate"], raw_action)
    timestamp = datetime.now(UTC)
    answers = [
        AnswerItem(
            question_id=question.question_id,
            field=question.field,
            value=_parse_answer(form[f"answer_{index}"][0], question),
            question=question.question,
            reason=question.reason,
            possible_decision_impact=_clinical_reason(question),
            responder_role=role,
            answered_at=timestamp,
            response_method="interactive_browser",
        )
        for index, question in enumerate(session.questions)
    ]
    answer_file = AnswerFile(answers=answers, interaction_action=action)
    return BrowserClarification(answer_file=answer_file, escalated=action == "escalate")


class _ClarificationHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    @property
    def _session(self) -> _Session:
        return cast(_Session, getattr(self.server, "clarification_session"))

    def _headers(self, status: int, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Security-Policy", _SECURITY_POLICY)
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()

    def _authorized(self, expected_path: str) -> bool:
        host = self.headers.get("Host")
        session = self._session
        return self.path == expected_path and host == f"127.0.0.1:{session.port}"

    def _respond(self, status: int, text: str) -> None:
        self._headers(status)
        self.wfile.write(text.encode("utf-8"))

    def do_GET(self) -> None:
        session = self._session
        if not self._authorized(f"/{session.token}") or session.outcome is not None:
            self._respond(404, "Page indisponible")
            return
        self._respond(200, _render_form(session))

    def _content_length(self) -> int | None:
        content_type = self.headers.get("Content-Type", "")
        raw_length = self.headers.get("Content-Length")
        if not content_type.startswith("application/x-www-form-urlencoded") or not raw_length:
            return None
        try:
            return int(raw_length)
        except ValueError:
            return None

    def do_POST(self) -> None:
        session = self._session
        if not self._authorized(f"/{session.token}/submit") or session.outcome is not None:
            self._respond(404, "Page indisponible")
            return
        length = self._content_length()
        if length is None:
            self._respond(400, "Requête invalide")
            return
        if length < 0 or length > _MAX_BODY_BYTES:
            self._respond(413, "Requête trop volumineuse")
            return
        try:
            outcome = _parse_submission(self.rfile.read(length), session)
        except (ValueError, TypeError):
            self._respond(400, "Réponses invalides")
            return
        session.outcome = outcome
        self._respond(200, "Réponses enregistrées. Vous pouvez fermer cette fenêtre.")


def collect_clinician_answers(
    questions: list[MissingQuestion],
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    opener: Callable[[str], bool] = webbrowser.open_new_tab,
    server_factory: type[HTTPServer] = HTTPServer,
) -> BrowserClarification | None:
    """Open one short-lived loopback form and return typed answers, if submitted."""

    if not questions:
        return None
    session = _Session(token=secrets.token_urlsafe(32), questions=questions)
    server = server_factory(("127.0.0.1", 0), _ClarificationHandler)
    setattr(server, "clarification_session", session)
    session.port = int(server.server_address[1])
    url = f"http://127.0.0.1:{session.port}/{session.token}"
    try:
        try:
            opened = opener(url)
        except Exception:
            return None
        if not opened:
            return None
        deadline = time.monotonic() + timeout_seconds
        while session.outcome is None and time.monotonic() < deadline:
            server.timeout = min(0.25, max(0.0, deadline - time.monotonic()))
            server.handle_request()
        return session.outcome
    finally:
        server.server_close()


def next_interactive_answer_path(output_dir: Path) -> Path:
    """Choose a new answer filename without replacing an earlier interaction."""

    for index in range(1, 1000):
        candidate = output_dir / f"answers.interactive.{index}.json"
        if not candidate.exists():
            return candidate
    raise ConfigurationError("No available interactive answer filename in the output directory.")


def write_interactive_answers(path: Path, answer_file: AnswerFile) -> None:
    """Write one private answer file without overwriting an existing record."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise ConfigurationError(f"Interactive answer file already exists: {path}") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(answer_file.model_dump(mode="json"), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
