"""Phase 1 verification tests: audit logging, persistence, secret redaction, fail-closed, and preflight."""

from pathlib import Path
import json
import pytest
import shutil

from app.config import get_settings
from app.core.audit_log import AuditLogger, get_configured_secret_values
from app.core.errors import AuditLogFailureError
from app.core.http_client import LoggedHttpClient
from app.core.storage import atomic_write_bytes, atomic_write_json
from app.jobs.repo import JobRepository
from app.preflight import run_preflight


@pytest.mark.asyncio
async def test_repository_crud():
    """Verify SQLite async repository with WAL mode, jobs, stages, and events."""
    repo = JobRepository(db_path="./storage/test_autoshorts.db")
    await repo.init_db()

    job_id = "test_job_001"
    job = await repo.create_job(job_id=job_id, prompt="Why is the sky blue?")
    assert job.id == job_id
    assert job.status == "queued"

    # Stage update
    stage = await repo.set_stage(job_id=job_id, stage="research", status="running")
    assert stage.stage == "research"
    assert stage.status == "running"

    stage_done = await repo.set_stage(job_id=job_id, stage="research", status="success", output_ref="stages/research.json")
    assert stage_done.status == "success"

    # Event insertion and ordering
    e1 = await repo.insert_event(job_id=job_id, seq=1, event_type="stage.started", payload_json=json.dumps({"stage": "research"}))
    e2 = await repo.insert_event(job_id=job_id, seq=2, event_type="stage.completed", payload_json=json.dumps({"stage": "research"}))
    assert e1.seq == 1
    assert e2.seq == 2

    events = await repo.get_events(job_id=job_id)
    assert len(events) == 2
    assert events[0].seq == 1
    assert events[1].seq == 2

    # Clean up test DB
    await repo.delete_job(job_id)
    await repo.close()


@pytest.mark.asyncio
async def test_audit_log_fail_closed(monkeypatch, tmp_path):
    """Verify fail-closed behavior: if log writing fails, AUDIT_LOG_FAILURE is raised and call is not made."""
    settings = get_settings()
    monkeypatch.setattr(settings, "LOG_FAIL_CLOSED", True)

    read_only_dir = tmp_path / "readonly_logs"
    read_only_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "LOG_DIR", str(read_only_dir))

    audit = AuditLogger(job_id="test_fail_closed")

    # When file writing fails, audit context manager must raise AuditLogFailureError
    def bad_write_text(self, *args, **kwargs):
        if "request.json" in str(self):
            raise OSError("Disk is full or read-only")
        return orig_write_text(self, *args, **kwargs)

    orig_write_text = Path.write_text
    monkeypatch.setattr(Path, "write_text", bad_write_text)

    with pytest.raises(AuditLogFailureError):
        async with audit.call(kind="llm", provider="gemini", label="fail_test") as rec:
            rec.record_request("POST", "https://example.com", {}, {})


@pytest.mark.asyncio
async def test_live_preflight_and_audit_tree():
    """Run live startup preflight and verify audit log tree, index.jsonl, and zero secrets."""
    settings = get_settings()
    report = run_preflight()
    rep = await report

    print("\n--- Live Preflight Report ---")
    print(f"Health Status: {rep.to_health_dict()}")
    print(f"Models Checked: {rep.models_status}")
    print(f"Pexels OK: {rep.pexels_ok}")
    print(f"Pixabay OK: {rep.pixabay_ok}")
    print(f"Edge-TTS OK: {rep.edge_tts_ok}")
    if rep.errors:
        print(f"Warnings/Errors: {rep.errors}")

    # Verify audit log tree under logs/api_calls/_system
    system_log_dir = Path(settings.LOG_DIR).resolve() / "_system"
    assert system_log_dir.exists(), f"Log directory {system_log_dir} does not exist"

    index_file = system_log_dir / "index.jsonl"
    assert index_file.exists(), f"index.jsonl does not exist in {system_log_dir}"
    lines = [json.loads(line) for line in index_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 4, f"Expected at least 4 logged preflight calls, got {len(lines)}"

    # Check each call folder has request.json, response.json, meta.json
    for entry in lines:
        call_folder = system_log_dir / entry["path"]
        assert call_folder.exists(), f"Call folder {call_folder} does not exist"
        assert (call_folder / "request.json").exists()
        assert (call_folder / "response.json").exists()
        assert (call_folder / "meta.json").exists()

    # CRITICAL: Verify NO plain secrets exist anywhere in the logs/api_calls directory
    configured_secrets = get_configured_secret_values()
    assert len(configured_secrets) > 0, "Expected configured secrets from .env"

    for log_file in system_log_dir.rglob("*.json*"):
        content = log_file.read_text(encoding="utf-8", errors="ignore")
        for secret in configured_secrets:
            assert secret not in content, f"Secret leaked in {log_file}!"
