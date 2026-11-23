"""
Caption length check, engine side: the reading rule of the caption sidecar, the
status logic (ok / too long / unverifiable, never a reassuring default), the
process boundary with the OneTrainer helper (simulated here, never launched),
the helper's own protocol (with fake `transformers` / `huggingface_hub`
modules) and the flat export rows. Nothing here loads a real
tokenizer, touches the network or uses a GPU; the real helper is verified by a
separate, explicitly authorized check. The CSV storage has its own module.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from src.engines import caption_length_check as clc
from src.engines import caption_token_helper as helper
from src.engines.onetrainer_launch import _TRAIN_REMOTE_SCRIPT_RELATIVE_PARTS, _VENV_PYTHON_RELATIVE_PARTS

LIMIT = 75


def tokenizer_info(name, error=None):
    return {
        "name": name, "repo_id": "stabilityai/stable-diffusion-xl-base-1.0", "subfolder": name,
        "revision": "462165984030d82259a11f4367a4eed129e94a7b", "class": "CLIPTokenizer",
        "model_max_length": 77 if error is None else None,
        "special_tokens_per_sequence": 2 if error is None else None,
        "content_limit": LIMIT if error is None else None, "error": error,
    }


def count_for(tokens):
    over = tokens > LIMIT
    return {
        "content_tokens": tokens, "special_tokens": 2, "over": over,
        "kept_text": "kept" if over else None, "truncated_text": "tail" if over else None,
    }


class FakeRunner:
    """Stands in for subprocess.run: one word of the line is one token."""

    def __init__(self, tokenizer_errors=(None, None), line_override=None, returncode=0, stdout=None,
                 stderr=b"", raises=None):
        self.tokenizer_errors = tokenizer_errors
        self.line_override = line_override or {}
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.raises = raises
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if self.raises is not None:
            raise self.raises
        if self.stdout is not None:
            output = self.stdout
        else:
            request = json.loads(kwargs["input"].decode("ascii"))
            results = []
            for line in request["lines"]:
                counts = []
                for index, error in enumerate(self.tokenizer_errors):
                    if error is not None:
                        counts.append(None)
                    elif line in self.line_override and self.line_override[line][index] is not None:
                        counts.append(self.line_override[line][index])
                    else:
                        counts.append(count_for(len(line.split())))
                results.append({"counts": counts})
            output = json.dumps({
                "protocol": 1, "ok": True,
                "tokenizers": [tokenizer_info("tokenizer", self.tokenizer_errors[0]),
                               tokenizer_info("tokenizer_2", self.tokenizer_errors[1])],
                "results": results, "meta": {"transformers": "fake", "torch_imported": False,
                                             "cuda_initialized": False},
            }).encode("ascii")
        return subprocess.CompletedProcess(args, self.returncode, stdout=output, stderr=self.stderr)


def words(n):
    return " ".join(["w"] * n)


def item(image_id, text, origin="entry", file_name=None):
    return {"image_id": image_id, "file_name": file_name or f"{image_id}.png",
            "concept_file_name": file_name or f"{image_id}.png", "text": text, "origin": origin}


class CaptionLinesTest(unittest.TestCase):

    def test_lines_are_stripped_and_empty_lines_dropped(self):
        self.assertEqual(clc.caption_lines("  a b  \n\n  c  \n   \nd"), ["a b", "c", "d"])

    def test_nothing_left_falls_back_to_a_single_empty_text(self):
        for text in ("", "   ", "\n\r\n \n"):
            with self.subTest(text=text):
                self.assertEqual(clc.caption_lines(text), [""])

    def test_universal_newlines_split_on_crlf_cr_and_lf_only(self):
        self.assertEqual(clc.caption_lines("a\r\nb\rc\nd"), ["a", "b", "c", "d"])
        # str.splitlines() would also split here; the sidecar reader does not.
        self.assertEqual(clc.caption_lines("a b"), ["a b"])


class FingerprintTest(unittest.TestCase):

    def test_same_inputs_same_fingerprint_and_any_change_changes_it(self):
        items = [item("i1", "a b"), item("i2", "c", origin="trigger_word")]
        base = clc.fingerprint_caption_inputs("t1", "SDXL", items)
        self.assertEqual(base, clc.fingerprint_caption_inputs("t1", "SDXL", [dict(x) for x in items]))
        self.assertNotEqual(base, clc.fingerprint_caption_inputs("t2", "SDXL", items))
        self.assertNotEqual(base, clc.fingerprint_caption_inputs("t1", "SD15", items))
        self.assertNotEqual(base, clc.fingerprint_caption_inputs("t1", "SDXL", [item("i1", "a b "), items[1]]))
        self.assertNotEqual(base, clc.fingerprint_caption_inputs("t1", "SDXL", [item("i1", "a b", "trigger_word"), items[1]]))
        self.assertNotEqual(base, clc.fingerprint_caption_inputs("t1", "SDXL", list(reversed(items))))
        self.assertNotEqual(base, clc.fingerprint_caption_inputs("t1", "SDXL", items, dataset_id="d2"))
        self.assertNotEqual(base, clc.fingerprint_caption_inputs("t1", "SDXL", items, onetrainer_path="C:/OT"))


class CheckCaptionLengthsTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        root = Path(self.tmp) / "OneTrainer"
        for parts in (_VENV_PYTHON_RELATIVE_PARTS, _TRAIN_REMOTE_SCRIPT_RELATIVE_PARTS):
            target = root.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"")
        self.onetrainer_path = str(root)
        self.python_executable = str(root.joinpath(*_VENV_PYTHON_RELATIVE_PARTS))

    def run_check(self, items, runner=None, architecture="SDXL", onetrainer_path=None, **kwargs):
        self.runner = runner or FakeRunner()
        return clc.check_caption_lengths(
            onetrainer_path=self.onetrainer_path if onetrainer_path is None else onetrainer_path,
            training_id="t1", training_name="Session 1", architecture=architecture,
            items=items, runner=self.runner, **kwargs,
        )

    def assert_never_reassuring(self, report):
        self.assertEqual(report.count(clc.STATUS_OK), 0)
        self.assertFalse(report.all_conform)
        self.assertFalse(report.complete)

    # --- nominal -------------------------------------------------------------------------------------------

    def test_conform_captions_give_a_complete_and_conform_report(self):
        report = self.run_check([item("i1", words(10)), item("i2", words(LIMIT))])

        self.assertEqual([r.status for r in report.items], [clc.STATUS_OK, clc.STATUS_OK])
        self.assertTrue(report.complete)
        self.assertTrue(report.all_conform)
        self.assertEqual(report.items[1].counts[0].content_tokens, LIMIT)
        self.assertEqual([t.usable for t in report.tokenizers], [True, True])

    def test_one_token_over_the_limit_is_too_long_and_keeps_the_decoded_tail(self):
        report = self.run_check([item("i1", words(LIMIT + 1))])

        result = report.items[0]
        self.assertEqual(result.status, clc.STATUS_TOO_LONG)
        self.assertEqual(result.counts[0].content_tokens, LIMIT + 1)
        self.assertEqual(result.counts[0].truncated_text, "tail")
        self.assertEqual(result.counts[0].truncated_line_index, 0)
        self.assertFalse(report.all_conform)
        self.assertTrue(report.complete)

    def test_the_request_is_offline_cpu_only_bounded_and_ascii(self):
        self.run_check([item("i1", "élégant « citation »")], timeout=33.0)

        args, kwargs = self.runner.calls[0]
        self.assertEqual(args[0], self.python_executable)
        self.assertEqual(args[1], "-I")
        self.assertEqual(Path(args[2]), clc.HELPER_PATH)
        self.assertEqual(kwargs["timeout"], 33.0)
        self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
        self.assertEqual(kwargs["env"]["TRANSFORMERS_OFFLINE"], "1")
        self.assertEqual(kwargs["env"]["CUDA_VISIBLE_DEVICES"], "")
        payload = kwargs["input"].decode("ascii")  # pure ASCII even with accents
        self.assertEqual(json.loads(payload), {"protocol": 1, "lines": ["élégant « citation »"]})

    def test_the_default_delay_is_bounded(self):
        self.run_check([item("i1", "a")])

        self.assertEqual(self.runner.calls[0][1]["timeout"], clc.CAPTION_CHECK_TIMEOUT_SECONDS)
        self.assertGreater(clc.CAPTION_CHECK_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(clc.CAPTION_CHECK_TIMEOUT_SECONDS, 300)

    # --- the text counted ----------------------------------------------------------------------------------

    def test_an_empty_caption_is_counted_as_one_empty_line_and_is_conform(self):
        report = self.run_check([item("i1", "", origin="entry")])

        self.assertEqual(json.loads(self.runner.calls[0][1]["input"].decode("ascii"))["lines"], [""])
        self.assertEqual(report.items[0].status, clc.STATUS_OK)
        self.assertEqual(report.items[0].origin, "entry")
        self.assertEqual(report.items[0].counts[0].content_tokens, 0)

    def test_a_multi_line_caption_is_analyzed_line_by_line_and_the_worst_line_decides(self):
        text = f"{words(5)}\n\n  {words(LIMIT + 3)}  \n{words(2)}"

        report = self.run_check([item("i1", text)])

        sent = json.loads(self.runner.calls[0][1]["input"].decode("ascii"))["lines"]
        self.assertEqual(sent, [words(5), words(LIMIT + 3), words(2)])
        result = report.items[0]
        self.assertEqual(result.line_count, 3)
        self.assertEqual(result.status, clc.STATUS_TOO_LONG)
        self.assertEqual(result.counts[0].content_tokens, LIMIT + 3)
        self.assertEqual(result.counts[0].over_line_count, 1)
        self.assertEqual(result.counts[0].truncated_line_index, 1)

    def test_the_answers_are_matched_back_to_their_own_caption(self):
        report = self.run_check([item("i1", words(3)), item("i2", words(LIMIT + 5)), item("i3", words(4))])

        self.assertEqual([r.status for r in report.items], [clc.STATUS_OK, clc.STATUS_TOO_LONG, clc.STATUS_OK])
        self.assertEqual([r.counts[0].content_tokens for r in report.items], [3, LIMIT + 5, 4])

    # --- tokenizers: partial failure never reassures --------------------------------------------------------

    def test_one_tokenizer_unavailable_makes_the_caption_unverifiable_not_ok(self):
        report = self.run_check([item("i1", words(5))], runner=FakeRunner(tokenizer_errors=(None, "cannot load")))

        result = report.items[0]
        self.assertEqual(result.status, clc.STATUS_UNVERIFIABLE)
        self.assertIn("cannot load", result.reason)
        self.assertIsNone(result.counts[1].content_tokens)
        self.assert_never_reassuring(report)

    def test_a_caption_over_the_limit_for_the_working_tokenizer_stays_too_long(self):
        report = self.run_check(
            [item("i1", words(LIMIT + 1))], runner=FakeRunner(tokenizer_errors=("cannot load", None))
        )

        self.assertEqual(report.items[0].status, clc.STATUS_TOO_LONG)
        self.assertFalse(report.all_conform)

    def test_disagreeing_tokenizers_are_too_long_when_only_one_exceeds(self):
        text = words(LIMIT)
        runner = FakeRunner(line_override={text: (count_for(LIMIT), count_for(LIMIT + 1))})

        report = self.run_check([item("i1", text)], runner=runner)

        self.assertEqual(report.items[0].status, clc.STATUS_TOO_LONG)
        self.assertEqual([c.content_tokens for c in report.items[0].counts], [LIMIT, LIMIT + 1])

    def test_a_line_without_a_count_makes_only_its_caption_unverifiable(self):
        text = words(7)
        runner = FakeRunner(line_override={text: ({"error": "boom"}, {"error": "boom"})})

        report = self.run_check([item("i1", words(3)), item("i2", text)], runner=runner)

        self.assertEqual([r.status for r in report.items], [clc.STATUS_OK, clc.STATUS_UNVERIFIABLE])
        self.assertFalse(report.complete)
        self.assertFalse(report.all_conform)

    # --- failures: everything unverifiable ------------------------------------------------------------------

    def test_unsupported_architecture_is_unverifiable_without_launching_anything(self):
        report = self.run_check([item("i1", "a")], architecture="SD15")

        self.assertEqual(self.runner.calls, [])
        self.assertEqual(report.items[0].status, clc.STATUS_UNVERIFIABLE)
        self.assertIn("not supported", report.reason)
        self.assert_never_reassuring(report)

    def test_unconfigured_or_missing_onetrainer_is_unverifiable_without_launching_anything(self):
        for path in ("", "   ", str(Path(self.tmp) / "absent")):
            with self.subTest(path=path):
                report = self.run_check([item("i1", "a")], onetrainer_path=path)
                self.assertEqual(self.runner.calls, [])
                self.assertEqual(report.items[0].status, clc.STATUS_UNVERIFIABLE)
                self.assertIn("OneTrainer is not usable", report.reason)
                self.assert_never_reassuring(report)

    def test_every_helper_failure_makes_everything_unverifiable(self):
        broken = {
            "timeout": FakeRunner(raises=subprocess.TimeoutExpired(cmd="x", timeout=1)),
            "cannot start": FakeRunner(raises=OSError("no such file")),
            "exit code": FakeRunner(returncode=3, stdout=b"", stderr=b"line\nTraceback: boom"),
            "unreadable": FakeRunner(stdout=b"not json"),
            "protocol": FakeRunner(stdout=json.dumps({"protocol": 9, "ok": True}).encode()),
            "refused": FakeRunner(stdout=json.dumps({"protocol": 1, "ok": False, "error": "bad"}).encode()),
            "no tokenizer": FakeRunner(stdout=json.dumps(
                {"protocol": 1, "ok": True, "tokenizers": [], "results": []}).encode()),
            "length": FakeRunner(stdout=json.dumps(
                {"protocol": 1, "ok": True, "tokenizers": [tokenizer_info("tokenizer")], "results": []}).encode()),
        }
        for label, runner in broken.items():
            with self.subTest(label):
                report = self.run_check([item("i1", "a"), item("i2", words(LIMIT + 4))], runner=runner)
                self.assertEqual([r.status for r in report.items], [clc.STATUS_UNVERIFIABLE] * 2)
                self.assertTrue(report.reason)
                self.assert_never_reassuring(report)

    def test_the_exit_code_failure_reports_the_last_error_line(self):
        report = self.run_check([item("i1", "a")], runner=FakeRunner(returncode=3, stdout=b"", stderr=b"x\nTraceback: boom"))

        self.assertIn("exit code 3", report.reason)
        self.assertIn("boom", report.reason)

    def test_the_delay_failure_names_the_bound(self):
        report = self.run_check(
            [item("i1", "a")], runner=FakeRunner(raises=subprocess.TimeoutExpired(cmd="x", timeout=7)), timeout=7.0
        )

        self.assertIn("did not finish within 7 s", report.reason)

    # --- multi-line captions: each line is judged on its own, like OneTrainer reads the sidecar -------------------

    def test_two_lines_under_the_limit_are_not_too_long_because_their_sum_is_over_it(self):
        report = self.run_check([item("i1", f"{words(40)}\n{words(40)}")])   # 80 tokens in all, 40 per line

        result = report.items[0]
        self.assertEqual(result.status, clc.STATUS_OK)
        self.assertEqual(result.line_count, 2)
        self.assertEqual([c.content_tokens for c in result.counts], [40, 40])
        self.assertEqual([c.over_line_count for c in result.counts], [0, 0])

    def test_a_single_long_line_is_reported_with_its_number_and_the_counts_of_each_tokenizer(self):
        long_line = words(80)
        runner = FakeRunner(line_override={long_line: (count_for(80), count_for(78))})

        report = self.run_check([item("i1", f"{words(10)}\n{long_line}\n{words(5)}")], runner=runner)

        result = report.items[0]
        first, second = result.counts
        self.assertEqual(result.status, clc.STATUS_TOO_LONG)
        self.assertEqual((first.content_tokens, second.content_tokens), (80, 78))
        self.assertEqual((first.truncated_line_number, second.truncated_line_number), (2, 2))
        self.assertEqual((first.longest_line_number, second.longest_line_number), (2, 2))
        row = clc.report_rows(report)[0]
        self.assertEqual((row["tokenizer_1_content_tokens"], row["tokenizer_2_content_tokens"]), (80, 78))
        self.assertEqual((row["tokenizer_1_truncated_line"], row["tokenizer_2_truncated_line"]), (2, 2))
        self.assertEqual((row["tokenizer_1_longest_line"], row["tokenizer_2_longest_line"]), (2, 2))

    def test_blank_lines_and_surrounding_whitespace_are_removed_before_counting_like_onetrainer(self):
        report = self.run_check([item("i1", "  alpha beta  \n\n   \n\t gamma \r\n")])

        self.assertEqual(json.loads(self.runner.calls[0][1]["input"].decode("ascii"))["lines"], ["alpha beta", "gamma"])
        self.assertEqual(report.items[0].line_count, 2)
        self.assertTrue(report.items[0].usable_text)

    # --- empty texts: "conform" only means "no excessive length" ----------------------------------------------------

    def test_a_text_with_nothing_usable_is_conform_for_length_only_and_flagged_without_any_replacement(self):
        items = [item("i1", ""), item("i2", " \n \r\n"), item("i3", "x y")]

        report = self.run_check(items)

        self.assertEqual([r.status for r in report.items], [clc.STATUS_OK] * 3)
        self.assertEqual([r.usable_text for r in report.items], [False, False, True])
        self.assertEqual(report.empty_count, 2)
        # Nothing replaces an empty text — in particular not the trigger word: the empty text itself is counted.
        self.assertEqual(json.loads(self.runner.calls[0][1]["input"].decode("ascii"))["lines"], ["", "", "x y"])
        self.assertEqual([row["usable_text"] for row in clc.report_rows(report)], ["no", "no", "yes"])

    def test_a_trigger_word_fallback_is_counted_as_that_text_only(self):
        report = self.run_check([item("i1", "Kaëlya woman", origin="trigger_word")])

        self.assertEqual(json.loads(self.runner.calls[0][1]["input"].decode("ascii"))["lines"], ["Kaëlya woman"])
        self.assertEqual(report.items[0].origin, "trigger_word")

    # --- helper messages are never hidden ---------------------------------------------------------------------------

    EXPECTED_WARNING = (
        "Token indices sequence length is longer than the specified maximum sequence length for this model "
        "(78 > 77). Running this sequence through the model will result in indexing errors"
    )

    def test_helper_messages_stay_visible_and_only_the_expected_length_warning_is_removed(self):
        stderr = (self.EXPECTED_WARNING + "\nSome real warning\n  \n" + self.EXPECTED_WARNING + " and more\n").encode()

        report = self.run_check([item("i1", "a")], runner=FakeRunner(stderr=stderr))

        self.assertEqual(report.helper_messages, ["Some real warning", self.EXPECTED_WARNING + " and more"])
        self.assertEqual(report.items[0].status, clc.STATUS_OK)

    def test_the_expected_warning_alone_leaves_no_message(self):
        report = self.run_check([item("i1", "a")], runner=FakeRunner(stderr=(self.EXPECTED_WARNING + "\n").encode()))

        self.assertEqual(report.helper_messages, [])

    def test_the_helper_output_accompanies_every_failure(self):
        cases = {
            "unreadable": FakeRunner(stdout=b"not json", stderr=b"ImportError: no module named transformers"),
            "protocol": FakeRunner(stdout=json.dumps({"protocol": 9, "ok": True}).encode(), stderr=b"odd protocol"),
            "refused": FakeRunner(stdout=json.dumps({"protocol": 1, "ok": False, "error": "bad"}).encode(),
                                  stderr=b"refusal detail"),
            "timeout": FakeRunner(raises=subprocess.TimeoutExpired(cmd="x", timeout=7, stderr=b"loading tokenizers")),
            "exit code": FakeRunner(returncode=1, stdout=b"", stderr=b"a\nb\nc\nTraceback: boom"),
        }
        expected = {"unreadable": "ImportError", "protocol": "odd protocol", "refused": "refusal detail",
                    "timeout": "loading tokenizers", "exit code": "boom"}
        for label, runner in cases.items():
            with self.subTest(label):
                report = self.run_check([item("i1", "a")], runner=runner)
                self.assertEqual(report.items[0].status, clc.STATUS_UNVERIFIABLE)
                self.assertIn(expected[label], report.reason)

    def test_a_missing_tokenizer_source_stays_visible_in_the_reason(self):
        error = "no local cache snapshot of stabilityai/stable-diffusion-xl-base-1.0: not cached"
        report = self.run_check([item("i1", "a")], runner=FakeRunner(tokenizer_errors=(error, error)))

        self.assertEqual(report.items[0].status, clc.STATUS_UNVERIFIABLE)
        self.assertIn("no local cache snapshot", report.items[0].reason)
        self.assertEqual([t.error for t in report.tokenizers], [error, error])
        self.assert_never_reassuring(report)

    def test_a_cancelled_runner_gives_an_unverifiable_report_without_launching_anything(self):
        runner = clc.HelperProcessRunner()
        runner.cancel()

        report = self.run_check([item("i1", "a")], runner=runner)

        self.assertEqual(report.items[0].status, clc.STATUS_UNVERIFIABLE)
        self.assertIn("cancelled", report.reason)

    # --- report and export rows ------------------------------------------------------------------------------

    def test_report_rows_identify_each_image_and_carry_both_counts_limits_and_status(self):
        report = self.run_check([
            item("i1", "élégant, « texte »\nligne 2", origin="entry", file_name="a.png"),
            item("i2", words(LIMIT + 2), origin="trigger_word", file_name="b.png"),
        ])

        rows = clc.report_rows(report)

        self.assertEqual(tuple(rows[0].keys()), clc.REPORT_COLUMNS)
        first, second = rows
        self.assertEqual((first["training_id"], first["training_name"]), ("t1", "Session 1"))
        self.assertEqual((first["image_id"], first["file_name"], first["concept_file_name"]), ("i1", "a.png", "a.png"))
        self.assertEqual(first["analyzed_text"], "élégant, « texte »\nligne 2")
        self.assertEqual(first["text_origin"], "entry")
        self.assertEqual(first["line_count"], 2)
        self.assertEqual((first["content_limit"], first["max_length"]), (LIMIT, 77))
        self.assertEqual((first["tokenizer_1_special_tokens"], first["tokenizer_2_special_tokens"]), (2, 2))
        self.assertEqual(first["status"], clc.STATUS_OK)
        self.assertEqual(second["text_origin"], "trigger_word")
        self.assertEqual((second["tokenizer_1_content_tokens"], second["tokenizer_2_content_tokens"]), (LIMIT + 2, LIMIT + 2))
        self.assertEqual(second["status"], clc.STATUS_TOO_LONG)
        self.assertEqual(second["truncated_text_tokenizer_1"], "tail")
        self.assertEqual(second["truncated_text_method"], "token_decode")
        self.assertEqual(second["texts_fingerprint"], report.fingerprint)
        self.assertIn("stabilityai/stable-diffusion-xl-base-1.0@462165984030/tokenizer", second["tokenizer_1_source"])

    def test_report_rows_of_an_unverifiable_check_have_empty_counts_and_the_reason(self):
        report = self.run_check([item("i1", "a")], architecture="SD15")

        row = clc.report_rows(report)[0]

        self.assertEqual(row["status"], clc.STATUS_UNVERIFIABLE)
        self.assertIn("not supported", row["status_reason"])
        self.assertEqual((row["tokenizer_1_content_tokens"], row["tokenizer_2_content_tokens"]), ("", ""))
        self.assertEqual((row["content_limit"], row["max_length"]), ("", ""))

    def test_no_item_gives_an_empty_report_that_is_not_reassuring(self):
        report = self.run_check([])

        self.assertEqual(report.total, 0)
        self.assertFalse(report.all_conform)


def _alive(pid):
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _wait_gone(pid, seconds=6.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.1)
    return not _alive(pid)


class HelperProcessRunnerTest(unittest.TestCase):
    """Real, harmless processes (the Python of this venv sleeping): nothing is ever left running."""

    PARENT_SCRIPT = (
        "import os, subprocess, sys, time\n"
        "grandchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "open(sys.argv[1], 'w').write(str(os.getpid()) + ' ' + str(grandchild.pid))\n"
        "time.sleep(120)\n"
    )

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pid_file = Path(self.tmp) / "pids.txt"

    def pids(self, wait=8.0):
        deadline = time.time() + wait
        while time.time() < deadline:
            if self.pid_file.exists() and self.pid_file.read_text().strip().count(" ") == 1:
                parent, grandchild = (int(x) for x in self.pid_file.read_text().split())
                return parent, grandchild
            time.sleep(0.05)
        self.fail("the test process never wrote its pids")

    def test_a_normal_run_returns_the_output_like_subprocess_run(self):
        completed = clc.HelperProcessRunner()(
            [sys.executable, "-c", "import sys; sys.stdout.write('out'); sys.stderr.write('err')"],
            input=b"", capture_output=True, timeout=30, env=dict(os.environ),
        )

        self.assertEqual((completed.returncode, completed.stdout, completed.stderr), (0, b"out", b"err"))

    def test_on_expiry_the_whole_process_tree_is_killed_and_nothing_stays_active(self):
        runner = clc.HelperProcessRunner()
        started = time.time()

        with self.assertRaises(subprocess.TimeoutExpired):
            runner([sys.executable, "-c", self.PARENT_SCRIPT, str(self.pid_file)],
                   input=b"", capture_output=True, timeout=3.0, env=dict(os.environ))

        self.assertLess(time.time() - started, 20)
        parent, grandchild = self.pids()
        self.assertTrue(_wait_gone(parent), "the launched process is still running")
        self.assertTrue(_wait_gone(grandchild), "a child of the launched process is still running")
        self.assertNotIn(runner, clc._ACTIVE_RUNNERS)

    def test_cancelling_stops_a_run_in_flight_with_its_children_and_refuses_new_runs(self):
        runner = clc.HelperProcessRunner()
        outcome = {}

        def run():
            try:
                runner([sys.executable, "-c", self.PARENT_SCRIPT, str(self.pid_file)],
                        input=b"", capture_output=True, timeout=60, env=dict(os.environ))
                outcome["done"] = True
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = exc

        thread = threading.Thread(target=run)
        thread.start()
        parent, grandchild = self.pids()
        runner.cancel()
        thread.join(30)

        self.assertFalse(thread.is_alive())
        self.assertTrue(runner.cancelled)
        self.assertTrue(_wait_gone(parent))
        self.assertTrue(_wait_gone(grandchild))
        with self.assertRaises(clc.CaptionLengthCheckError):
            runner([sys.executable, "-c", "pass"], input=b"", capture_output=True, timeout=5, env=dict(os.environ))


class CaptionTokenHelperProtocolTest(unittest.TestCase):
    """The helper's protocol, with fake `huggingface_hub` and `transformers`: no real tokenizer."""

    class FakeTokenizer:
        def __init__(self, max_length=77):
            self.model_max_length = max_length

        def __call__(self, text, add_special_tokens=True, truncation=False):
            ids = list(range(10, 10 + len(text.split())))
            return {"input_ids": ([49406] + ids + [49407]) if add_special_tokens else ids}

        def decode(self, ids, skip_special_tokens=True):
            return " ".join(f"t{i}" for i in ids)

    def run_helper(self, request, snapshot_error=None, bad_subfolder=None, max_length=77):
        observed = {}

        def snapshot_download(repo_id, local_files_only=False, allow_patterns=None):
            observed["env"] = {key: os.environ.get(key) for key in
                               ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "CUDA_VISIBLE_DEVICES")}
            observed["local_files_only"] = local_files_only
            observed["repo_id"] = repo_id
            if snapshot_error is not None:
                raise snapshot_error
            return os.path.join("cache", "snapshots", "abc123def456")

        outer = self

        class FakeCLIPTokenizer:
            @staticmethod
            def from_pretrained(path, subfolder=None, local_files_only=False):
                observed.setdefault("loads", []).append((subfolder, local_files_only))
                if subfolder == bad_subfolder:
                    raise OSError("missing tokenizer files")
                return outer.FakeTokenizer(max_length)

        modules = {
            "huggingface_hub": type(sys)("huggingface_hub"),
            "transformers": type(sys)("transformers"),
        }
        modules["huggingface_hub"].snapshot_download = snapshot_download
        modules["transformers"].CLIPTokenizer = FakeCLIPTokenizer
        modules["transformers"].__version__ = "fake"

        stdin = type("In", (), {"buffer": io.BytesIO(request if isinstance(request, bytes)
                                                     else json.dumps(request).encode("utf-8"))})()
        stdout = type("Out", (), {"buffer": io.BytesIO()})()
        with patch.dict(sys.modules, modules), patch.dict(os.environ), \
                patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
            code = helper.main()
        raw = stdout.buffer.getvalue()
        raw.decode("ascii")  # the answer is always pure ASCII
        return code, json.loads(raw), observed

    def test_counts_content_tokens_apart_from_special_tokens_and_marks_the_limit(self):
        code, answer, _ = self.run_helper({"protocol": 1, "lines": ["", "a b", " ".join(["w"] * 75), " ".join(["w"] * 76)]})

        self.assertEqual(code, 0)
        self.assertTrue(answer["ok"])
        for info in answer["tokenizers"]:
            self.assertEqual((info["model_max_length"], info["special_tokens_per_sequence"], info["content_limit"]),
                             (77, 2, 75))
            self.assertIsNone(info["error"])
        counts = [result["counts"][0] for result in answer["results"]]
        self.assertEqual([c["content_tokens"] for c in counts], [0, 2, 75, 76])
        self.assertEqual([c["special_tokens"] for c in counts], [2, 2, 2, 2])
        self.assertEqual([c["over"] for c in counts], [False, False, False, True])

    def test_the_truncated_part_is_the_decoded_tail_after_the_limit(self):
        _, answer, _ = self.run_helper({"protocol": 1, "lines": [" ".join(["w"] * 77)]})

        count = answer["results"][0]["counts"][0]
        self.assertTrue(count["over"])
        self.assertTrue(count["kept_text"].endswith("t84"))      # ids 10..84 are the 75 kept tokens
        self.assertEqual(count["truncated_text"], "t85 t86")

    def test_both_sdxl_tokenizers_come_from_the_local_cache_snapshot_in_order(self):
        _, answer, observed = self.run_helper({"protocol": 1, "lines": ["a"]})

        self.assertEqual([t["subfolder"] for t in answer["tokenizers"]], ["tokenizer", "tokenizer_2"])
        self.assertEqual(answer["tokenizers"][0]["repo_id"], "stabilityai/stable-diffusion-xl-base-1.0")
        self.assertEqual(answer["tokenizers"][0]["revision"], "abc123def456")
        self.assertEqual(observed["repo_id"], "stabilityai/stable-diffusion-xl-base-1.0")
        self.assertEqual(observed["loads"], [("tokenizer", True), ("tokenizer_2", True)])

    def test_offline_and_cpu_only_flags_are_forced_before_anything_is_resolved(self):
        _, _, observed = self.run_helper({"protocol": 1, "lines": ["a"]})

        self.assertTrue(observed["local_files_only"])
        self.assertEqual(observed["env"], {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "CUDA_VISIBLE_DEVICES": ""})

    def test_an_incompatible_model_max_length_disables_the_tokenizer(self):
        _, answer, _ = self.run_helper({"protocol": 1, "lines": ["a"]}, max_length=512)

        for info in answer["tokenizers"]:
            self.assertIn("unexpected model_max_length 512", info["error"])
        self.assertEqual(answer["results"][0]["counts"], [None, None])

    def test_a_missing_local_snapshot_substitutes_nothing(self):
        _, answer, _ = self.run_helper({"protocol": 1, "lines": ["a", "b"]}, snapshot_error=OSError("not cached"))

        self.assertTrue(answer["ok"])
        for info in answer["tokenizers"]:
            self.assertIn("no local cache snapshot", info["error"])
        self.assertEqual([r["counts"] for r in answer["results"]], [[None, None], [None, None]])

    def test_a_single_failing_tokenizer_leaves_the_other_one_counted(self):
        _, answer, _ = self.run_helper({"protocol": 1, "lines": ["a b"]}, bad_subfolder="tokenizer_2")

        self.assertIsNone(answer["tokenizers"][0]["error"])
        self.assertIn("missing tokenizer files", answer["tokenizers"][1]["error"])
        first, second = answer["results"][0]["counts"]
        self.assertEqual(first["content_tokens"], 2)
        self.assertIsNone(second)

    def test_accented_input_still_gives_an_ascii_only_answer(self):
        _, answer, _ = self.run_helper({"protocol": 1, "lines": ["Kaëlya élégant « x »"]})

        self.assertEqual(answer["results"][0]["counts"][0]["content_tokens"], 5)   # 5 words: one token each

    def test_invalid_requests_are_refused_with_a_json_answer(self):
        for request in (b"not json", {"protocol": 2, "lines": []}, {"protocol": 1, "lines": "x"},
                        {"protocol": 1, "lines": [1]}, {"protocol": 1}):
            with self.subTest(request=request):
                code, answer, _ = self.run_helper(request)
                self.assertEqual(code, 0)
                self.assertFalse(answer["ok"])
                self.assertIn("invalid request", answer["error"])


if __name__ == "__main__":
    unittest.main()
