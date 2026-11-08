import importlib
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
report = importlib.import_module('12_report')


def test_report_counts_successes_and_excludes_skips(tmp_path):
    path = tmp_path / 'run.xml'
    path.write_text('<testsuites><testsuite><testcase/><testcase><skipped/></testcase></testsuite></testsuites>', encoding="utf-8")
    assert report.tests_passed(path) == (1, 0)


@pytest.mark.parametrize('content', ['<testsuites/>', '<testsuites><testcase><failure/></testcase></testsuites>', '<testsuites><testcase><error/></testcase></testsuites>', '<testsuites><testcase><skipped/></testcase></testsuites>'])
def test_report_refuses_empty_failed_or_errored_evidence(tmp_path, content):
    path = tmp_path / 'run.xml'
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        report.tests_passed(path)


def test_report_refuses_failed_subprocess_even_if_output_mentions_passing_tests(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(report.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout='10 passed, 1 error', stderr='collection error'))
    with pytest.raises(ValueError):
        report.tests_passed()
