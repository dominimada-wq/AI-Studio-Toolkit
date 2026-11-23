"""
Caption length check for OneTrainer's supported SDXL training path.

Toolkit-side half of the check (the counting itself lives in
caption_token_helper.py, run as a separate process with OneTrainer's own
Python). This module never imports `transformers`/`tokenizers`/`torch`, knows
nothing about the Domain (it exchanges strings and dictionaries) and never
writes anything.

Three statuses per caption, never merged:
- STATUS_OK: no line exceeds the content limit for any tokenizer AND every
  tokenizer was verifiable. "Ok" only means "no excessive length": it says
  nothing about the quality of a caption, and an empty caption is "ok" too (see
  CaptionItemResult.usable_text);
- STATUS_TOO_LONG: at least one tokenizer counts more content tokens than the
  limit on at least one line (the end of that line is silently truncated by
  OneTrainer);
- STATUS_UNVERIFIABLE: the count could not be established (architecture not
  supported, OneTrainer not configured, helper failure or timeout, tokenizer
  not found or incompatible, one tokenizer failing). A partial failure is never
  rounded up to "ok": TOO_LONG wins over UNVERIFIABLE, UNVERIFIABLE wins over OK.

The text counted is the text of the caption sidecar OneTrainer reads, line by
line: mgds/pipelineModules/LoadMultipleTexts.py reads the file with
`[line.strip() for line in f]`, drops empty lines and falls back to a single
empty text, then each line is tokenized separately with truncation
(Tokenize.py). `caption_lines()` reproduces exactly that reading: two lines that
are each under the limit are never "too long" because their sum is over it.
When nothing usable is left, OneTrainer trains on an empty text: nothing, in
particular not the trigger word, replaces it, and this module does not invent
any replacement either.

The helper process is bounded in time and, whatever happens (delay elapsed,
cancellation, application exit), its whole process tree is terminated: no
counting process is left running.
"""

import atexit
import hashlib
import json
import os
import re
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from src.engines.onetrainer_launch import OneTrainerLaunchError, resolve_onetrainer_launch

SUPPORTED_ARCHITECTURE = "SDXL"

STATUS_OK = "ok"
STATUS_TOO_LONG = "too_long"
STATUS_UNVERIFIABLE = "unverifiable"

# The first run of the helper imports transformers (and, through it, torch) cold:
# about 30 s were measured. A generous but bounded delay; the process tree is
# killed when it elapses.
CAPTION_CHECK_TIMEOUT_SECONDS = 120.0

PROTOCOL = 1
HELPER_PATH = Path(__file__).resolve().with_name("caption_token_helper.py")

TRUNCATED_TEXT_METHOD = "token_decode"

_LINE_SPLIT = re.compile(r"\r\n|\r|\n")

# The one warning the helper is expected to trigger: it tokenizes WITHOUT
# truncation on purpose, which makes `transformers` warn when a line is longer
# than the model maximum. Nothing else on stderr is ever hidden.
_EXPECTED_LENGTH_WARNING = re.compile(
    r"Token indices sequence length is longer than the specified maximum sequence length "
    r"for this model \(\d+ > \d+\)\. Running this sequence through the model will result in indexing errors\.?"
)


class CaptionLengthCheckError(Exception):
    """The helper could not produce a usable answer (reason in the message)."""


def caption_lines(text: str) -> List[str]:
    """
    The texts OneTrainer actually tokenizes for one caption sidecar: the lines of
    the file, stripped, empty lines dropped, `[""]` when nothing remains. The
    sidecar is read in text mode with universal newlines, hence the split on
    "\\r\\n", "\\r" and "\\n" only (not `str.splitlines()`, which splits on more).
    """
    lines = [line.strip() for line in _LINE_SPLIT.split(text)]
    lines = [line for line in lines if line != ""]
    return lines if lines else [""]


def has_usable_text(text: str) -> bool:
    """False when OneTrainer would be left with no text at all after removing blank lines."""
    return any(line != "" for line in caption_lines(text))


def fingerprint_caption_inputs(training_id: str, architecture: str, items: List[dict],
                               dataset_id: str = "", onetrainer_path: str = "") -> str:
    """
    SHA-256 tying a result to everything it depends on: the training, its
    architecture and Dataset, the OneTrainer installation used and, per image,
    (image_id, text, origin). Changing any of them changes the fingerprint, so a
    stale result is detectable.
    """
    payload = [
        training_id,
        architecture,
        dataset_id,
        onetrainer_path,
        [[item["image_id"], item["text"], item["origin"]] for item in items],
    ]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


# --------------------------------------------------------------------------------------------------------
# Process handling: bounded, cancellable, never leaves a process behind
# --------------------------------------------------------------------------------------------------------

_ACTIVE_RUNNERS = set()
_ACTIVE_LOCK = threading.Lock()


def _terminate_tree(process: subprocess.Popen) -> None:
    """Kills `process` and every process it started (a Windows venv launcher starts a child)."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except Exception:  # noqa: BLE001 — falls back to killing the direct child below
        pass
    try:
        process.kill()
    except Exception:  # noqa: BLE001
        pass


def _terminate_all_active_runners() -> None:
    with _ACTIVE_LOCK:
        runners = list(_ACTIVE_RUNNERS)
    for runner in runners:
        runner.cancel()


atexit.register(_terminate_all_active_runners)


class HelperProcessRunner:
    """
    A `subprocess.run`-like callable for one helper launch, with what `run()`
    lacks here: on delay expiry the WHOLE process tree is killed (not only the
    direct child), `cancel()` can stop a launch in flight, and any launch still
    running at interpreter exit is killed. One instance serves one check.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            process = self._process
        if process is not None:
            _terminate_tree(process)

    def __call__(self, args, *, input=None, capture_output=True, timeout=None, env=None, creationflags=0):
        options = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "env": env}
        if os.name == "nt":
            options["creationflags"] = creationflags
        else:
            options["start_new_session"] = True
        with self._lock:
            if self._cancelled:
                raise CaptionLengthCheckError("the token counting was cancelled")
            process = subprocess.Popen(args, **options)
            self._process = process
        with _ACTIVE_LOCK:
            _ACTIVE_RUNNERS.add(self)
        try:
            try:
                stdout, stderr = process.communicate(input=input, timeout=timeout)
            except subprocess.TimeoutExpired:
                _terminate_tree(process)
                drained_output, drained_errors = b"", b""
                try:
                    drained_output, drained_errors = process.communicate(timeout=5)
                except Exception:  # noqa: BLE001 — the process is already killed; reaping is best effort
                    pass
                raise subprocess.TimeoutExpired(args, timeout, output=drained_output, stderr=drained_errors)
            return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_RUNNERS.discard(self)
            with self._lock:
                self._process = None


# --------------------------------------------------------------------------------------------------------
# Report model
# --------------------------------------------------------------------------------------------------------

@dataclass
class TokenizerInfo:
    name: str
    repo_id: str = ""
    subfolder: str = ""
    revision: str = ""
    tokenizer_class: str = ""
    model_max_length: Optional[int] = None
    special_tokens_per_sequence: Optional[int] = None
    content_limit: Optional[int] = None
    error: Optional[str] = None

    @property
    def usable(self) -> bool:
        return self.error is None and self.content_limit is not None

    @property
    def source(self) -> str:
        if not self.repo_id:
            return ""
        revision = f"@{self.revision[:12]}" if self.revision else ""
        return f"{self.repo_id}{revision}/{self.subfolder}"


@dataclass
class TokenizerItemCount:
    """What one tokenizer says about one caption: its longest line and the first line over the limit."""

    content_tokens: Optional[int] = None         # content tokens of the caption's longest line
    special_tokens: Optional[int] = None
    longest_line_index: Optional[int] = None     # 0-based index among the lines OneTrainer reads
    over_line_count: int = 0
    truncated_line_index: Optional[int] = None   # 0-based index of the first line over the limit
    truncated_text: Optional[str] = None         # decoded from tokens, for that first line
    error: Optional[str] = None

    @property
    def longest_line_number(self) -> Optional[int]:
        return None if self.longest_line_index is None else self.longest_line_index + 1

    @property
    def truncated_line_number(self) -> Optional[int]:
        return None if self.truncated_line_index is None else self.truncated_line_index + 1


@dataclass
class CaptionItemResult:
    image_id: str
    file_name: str
    text: str
    origin: str
    line_count: int
    status: str
    reason: str = ""
    counts: List[TokenizerItemCount] = field(default_factory=list)
    concept_image_file_name: str = ""     # name of the image in the concept folder (may differ from file_name)
    concept_caption_file_name: str = ""   # name of its caption file there (same stem, .txt)
    usable_text: bool = True   # False: nothing left after removing blank lines (OneTrainer trains on an empty text)


@dataclass
class CaptionLengthReport:
    training_id: str
    training_name: str
    architecture: str
    fingerprint: str
    tokenizers: List[TokenizerInfo]
    items: List[CaptionItemResult]
    reason: str = ""                          # global reason when everything is unverifiable
    helper_meta: dict = field(default_factory=dict)
    helper_messages: List[str] = field(default_factory=list)   # stderr lines of the helper, expected warning excluded

    def count(self, status: str) -> int:
        return sum(1 for item in self.items if item.status == status)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def empty_count(self) -> int:
        """Captions with no usable text at all (nothing replaces them)."""
        return sum(1 for item in self.items if not item.usable_text)

    @property
    def complete(self) -> bool:
        """True only when every caption could be verified."""
        return self.count(STATUS_UNVERIFIABLE) == 0

    @property
    def all_conform(self) -> bool:
        """The only state allowed to be presented as reassuring: complete, and nothing too long."""
        return self.total > 0 and self.count(STATUS_OK) == self.total


def _item_result(item: dict, status: str, reason: str, counts: List[TokenizerItemCount]) -> CaptionItemResult:
    lines = caption_lines(item["text"])
    return CaptionItemResult(
        image_id=item["image_id"], file_name=item["file_name"], text=item["text"], origin=item["origin"],
        line_count=len(lines), status=status, reason=reason, counts=counts,
        concept_image_file_name=item.get("concept_image_file_name", ""),
        concept_caption_file_name=item.get("concept_caption_file_name", ""),
        usable_text=has_usable_text(item["text"]),
    )


def unverifiable_report(training_id: str, training_name: str, architecture: str, fingerprint: str,
                        items: List[dict], reason: str, helper_messages: Optional[List[str]] = None) -> CaptionLengthReport:
    return CaptionLengthReport(
        training_id=training_id, training_name=training_name, architecture=architecture,
        fingerprint=fingerprint, tokenizers=[],
        items=[_item_result(item, STATUS_UNVERIFIABLE, reason, []) for item in items],
        reason=reason, helper_messages=list(helper_messages or []),
    )


def _helper_messages(stderr: bytes) -> List[str]:
    """The helper's stderr lines, minus the one expected length warning; everything else stays visible."""
    text = (stderr or b"").decode("utf-8", "replace")
    messages = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not _EXPECTED_LENGTH_WARNING.fullmatch(stripped):
            messages.append(stripped)
    return messages


def _run_helper(python_executable: str, lines: List[str], timeout: float, runner: Callable):
    """Returns (response dict, helper stderr messages); raises CaptionLengthCheckError with the messages."""
    environment = dict(os.environ)
    environment.update({
        "HF_HUB_OFFLINE": "1",            # no download, ever
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "CUDA_VISIBLE_DEVICES": "",        # CPU only
        "TOKENIZERS_PARALLELISM": "false",
        "PYTHONIOENCODING": "utf-8",
    })
    request = json.dumps({"protocol": PROTOCOL, "lines": lines}, ensure_ascii=True).encode("ascii")
    try:
        completed = runner(
            [python_executable, "-I", str(HELPER_PATH)],
            input=request, capture_output=True, timeout=timeout, env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raw_errors = exc.stderr if isinstance(exc.stderr, (bytes, bytearray)) else b""
        detail = _helper_messages(bytes(raw_errors))
        suffix = f" — helper output: {' | '.join(detail[-3:])}" if detail else ""
        raise CaptionLengthCheckError(
            f"the token counting did not finish within {timeout:g} s (the process was stopped){suffix}"
        ) from exc
    except OSError as exc:
        raise CaptionLengthCheckError(f"could not start OneTrainer's Python: {exc}") from exc

    messages = _helper_messages(completed.stderr)

    def with_messages(text: str) -> str:
        # The helper's own messages always accompany an error: nothing is hidden.
        return text + (f" — helper output: {' | '.join(messages[-3:])}" if messages else "")

    if completed.returncode != 0:
        tail = " | ".join(messages[-3:]) if messages else "no error output"
        raise CaptionLengthCheckError(
            f"the token counting process failed (exit code {completed.returncode}): {tail}"
        )
    try:
        response = json.loads(completed.stdout.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CaptionLengthCheckError(
            with_messages("the token counting process returned an unreadable answer")
        ) from exc
    if not isinstance(response, dict) or response.get("protocol") != PROTOCOL:
        raise CaptionLengthCheckError(
            with_messages("the token counting process returned an unexpected protocol")
        )
    if not response.get("ok"):
        raise CaptionLengthCheckError(
            with_messages(f"the token counting process refused the request: {response.get('error')}")
        )
    return response, messages


def _parse_tokenizers(response: dict) -> List[TokenizerInfo]:
    raw = response.get("tokenizers")
    if not isinstance(raw, list) or not raw:
        raise CaptionLengthCheckError("the answer lists no tokenizer")
    infos = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise CaptionLengthCheckError("a tokenizer entry is malformed")
        infos.append(TokenizerInfo(
            name=str(entry.get("name", "")), repo_id=str(entry.get("repo_id") or ""),
            subfolder=str(entry.get("subfolder") or ""), revision=str(entry.get("revision") or ""),
            tokenizer_class=str(entry.get("class") or ""),
            model_max_length=entry.get("model_max_length"),
            special_tokens_per_sequence=entry.get("special_tokens_per_sequence"),
            content_limit=entry.get("content_limit"),
            error=entry.get("error") if isinstance(entry.get("error"), str) else None,
        ))
    return infos


def _item_count(tokenizer_index: int, info: TokenizerInfo, line_answers: List[Optional[list]]) -> TokenizerItemCount:
    """Aggregates one tokenizer's answers over one caption's lines: each line is judged on its own."""
    if not info.usable:
        return TokenizerItemCount(error=info.error or "tokenizer not usable")
    count = TokenizerItemCount(content_tokens=0, special_tokens=info.special_tokens_per_sequence,
                               longest_line_index=0)
    for line_index, answers in enumerate(line_answers):
        answer = answers[tokenizer_index] if answers is not None and tokenizer_index < len(answers) else None
        if not isinstance(answer, dict) or "content_tokens" not in answer:
            error = answer.get("error") if isinstance(answer, dict) else None
            return TokenizerItemCount(error=error or "no count returned for this line")
        tokens = int(answer["content_tokens"])
        if tokens > count.content_tokens:
            count.content_tokens = tokens
            count.longest_line_index = line_index
        if answer.get("over"):
            count.over_line_count += 1
            if count.truncated_line_index is None:
                count.truncated_line_index = line_index
                count.truncated_text = answer.get("truncated_text") or ""
    return count


def _classify(counts: List[TokenizerItemCount]) -> tuple:
    if any(count.over_line_count > 0 for count in counts):
        return STATUS_TOO_LONG, ""
    failed = [count for count in counts if count.error is not None]
    if failed:
        return STATUS_UNVERIFIABLE, failed[0].error
    return STATUS_OK, ""


def check_caption_lengths(
    *,
    onetrainer_path: str,
    training_id: str,
    training_name: str,
    architecture: str,
    items: List[dict],
    dataset_id: str = "",
    timeout: float = CAPTION_CHECK_TIMEOUT_SECONDS,
    runner: Optional[Callable] = None,
) -> CaptionLengthReport:
    """
    items: dicts with image_id, file_name, text, origin (see
    TrainingManager.caption_analysis_inputs()). Always returns a report: every
    failure becomes STATUS_UNVERIFIABLE with its reason, never an exception and
    never a reassuring default. `runner` defaults to a HelperProcessRunner (kills
    the whole process tree on expiry); tests and cancellation pass their own.
    """
    fingerprint = fingerprint_caption_inputs(training_id, architecture, items, dataset_id, onetrainer_path)

    def unverifiable(reason: str, messages=None) -> CaptionLengthReport:
        return unverifiable_report(training_id, training_name, architecture, fingerprint, items, reason, messages)

    if architecture != SUPPORTED_ARCHITECTURE:
        return unverifiable(
            f"architecture {architecture or '(none)'} is not supported by this check "
            f"(only {SUPPORTED_ARCHITECTURE} was audited)"
        )
    try:
        launch = resolve_onetrainer_launch(onetrainer_path)
    except OneTrainerLaunchError as exc:
        return unverifiable(f"OneTrainer is not usable: {exc}")

    per_item_lines = [caption_lines(item["text"]) for item in items]
    flat_lines = [line for lines in per_item_lines for line in lines]
    runner = runner if runner is not None else HelperProcessRunner()

    try:
        response, messages = _run_helper(launch.python_executable, flat_lines, timeout, runner)
    except CaptionLengthCheckError as exc:
        return unverifiable(str(exc))
    try:
        infos = _parse_tokenizers(response)
        results = response.get("results")
        if not isinstance(results, list) or len(results) != len(flat_lines):
            raise CaptionLengthCheckError("the answer does not match the lines sent")
        counts_per_line = [result.get("counts") if isinstance(result, dict) else None for result in results]
    except CaptionLengthCheckError as exc:
        return unverifiable(str(exc), messages)

    item_results = []
    cursor = 0
    for item, lines in zip(items, per_item_lines):
        line_answers = counts_per_line[cursor:cursor + len(lines)]
        cursor += len(lines)
        counts = [_item_count(index, info, line_answers) for index, info in enumerate(infos)]
        status, reason = _classify(counts)
        item_results.append(_item_result(item, status, reason, counts))
    meta = response.get("meta") if isinstance(response.get("meta"), dict) else {}
    return CaptionLengthReport(
        training_id=training_id, training_name=training_name, architecture=architecture,
        fingerprint=fingerprint, tokenizers=infos, items=item_results, helper_meta=meta,
        helper_messages=messages,
    )


REPORT_COLUMNS = (
    "training_id", "training_name", "image_id", "file_name", "concept_image_file_name",
    "concept_caption_file_name", "text_origin", "usable_text",
    "line_count", "analyzed_text",
    "tokenizer_1_content_tokens", "tokenizer_1_special_tokens", "tokenizer_1_longest_line",
    "tokenizer_2_content_tokens", "tokenizer_2_special_tokens", "tokenizer_2_longest_line",
    "content_limit", "max_length", "status", "status_reason",
    "tokenizer_1_truncated_line", "truncated_text_tokenizer_1",
    "tokenizer_2_truncated_line", "truncated_text_tokenizer_2", "truncated_text_method",
    "tokenizer_1_source", "tokenizer_2_source", "texts_fingerprint",
)


def report_rows(report: CaptionLengthReport) -> List[dict]:
    """One flat row per image, columns in REPORT_COLUMNS order (see the CSV export). Line numbers are 1-based."""

    def info(index: int) -> Optional[TokenizerInfo]:
        return report.tokenizers[index] if index < len(report.tokenizers) else None

    def cell(value):
        return "" if value is None else value

    first, second = info(0), info(1)
    limits = {tokenizer.content_limit for tokenizer in report.tokenizers if tokenizer.usable}
    maxima = {tokenizer.model_max_length for tokenizer in report.tokenizers if tokenizer.usable}
    rows = []
    for item in report.items:
        count_1 = item.counts[0] if len(item.counts) > 0 else TokenizerItemCount()
        count_2 = item.counts[1] if len(item.counts) > 1 else TokenizerItemCount()
        rows.append({
            "training_id": report.training_id,
            "training_name": report.training_name,
            "image_id": item.image_id,
            "file_name": item.file_name,
            "concept_image_file_name": item.concept_image_file_name,
            "concept_caption_file_name": item.concept_caption_file_name,
            "text_origin": item.origin,
            "usable_text": "yes" if item.usable_text else "no",
            "line_count": item.line_count,
            "analyzed_text": item.text,
            "tokenizer_1_content_tokens": cell(count_1.content_tokens),
            "tokenizer_1_special_tokens": cell(count_1.special_tokens),
            "tokenizer_1_longest_line": cell(count_1.longest_line_number),
            "tokenizer_2_content_tokens": cell(count_2.content_tokens),
            "tokenizer_2_special_tokens": cell(count_2.special_tokens),
            "tokenizer_2_longest_line": cell(count_2.longest_line_number),
            "content_limit": next(iter(limits)) if len(limits) == 1 else "",
            "max_length": next(iter(maxima)) if len(maxima) == 1 else "",
            "status": item.status,
            "status_reason": item.reason,
            "tokenizer_1_truncated_line": cell(count_1.truncated_line_number),
            "truncated_text_tokenizer_1": cell(count_1.truncated_text),
            "tokenizer_2_truncated_line": cell(count_2.truncated_line_number),
            "truncated_text_tokenizer_2": cell(count_2.truncated_text),
            "truncated_text_method": TRUNCATED_TEXT_METHOD,
            "tokenizer_1_source": first.source if first else "",
            "tokenizer_2_source": second.source if second else "",
            "texts_fingerprint": report.fingerprint,
        })
    return rows
