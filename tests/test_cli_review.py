import gzip
import hashlib
import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "src" / "act_proxy_audit.py"


def _record(nct_id):
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct_id},
            "statusModule": {
                "primaryCompletionDateStruct": {"date": "2023-01-01", "type": "ACTUAL"}
            },
            "designModule": {"studyType": "INTERVENTIONAL"},
        },
        "hasResults": False,
    }


def test_cli_jsonl_metadata_checksum(tmp_path):
    source = tmp_path / "trials.jsonl.gz"
    with gzip.open(source, "wt", encoding="utf-8") as f:
        f.write(json.dumps(_record("NCT00000001")) + "\n")
    output = tmp_path / "review.jsonl"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(source),
         "--as-of", "2026-10-15", "--output", str(output)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(output.read_text())
    assert data["act_eligibility"] == "UNDETERMINED"
    assert data["results_legal_overdue_status"] == "UNDETERMINED"
    metadata = json.loads((tmp_path / "review.jsonl.metadata.json").read_text())
    assert metadata["records"] == 1
    assert metadata["source_input_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert metadata["derived_output_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_cli_does_not_publish_duplicate_or_partial_results(tmp_path):
    source = tmp_path / "dup.jsonl"
    source.write_text(
        json.dumps(_record("NCT00000001")) + "\n"
        + json.dumps(_record("NCT00000001")) + "\n", encoding="utf-8"
    )
    dest = tmp_path / "out.jsonl"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(source),
         "--as-of", "2026-10-15", "--output", str(dest)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "Duplicate source NCT ID" in result.stderr
    assert not dest.exists()
    assert not (tmp_path / "out.jsonl.partial").exists()


def test_cli_rejects_invalid_date_and_output_as_source(tmp_path):
    source = tmp_path / "a.jsonl"
    source.write_text(json.dumps(_record("NCT00000001")) + "\n")
    for cmd in [
        [sys.executable, str(SCRIPT), "--input", str(source),
         "--as-of", "2026-10", "--output", str(tmp_path / "o.jsonl")],
        [sys.executable, str(SCRIPT), "--input", str(source),
         "--as-of", "2026-10-15", "--output", str(source)],
    ]:
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode != 0
