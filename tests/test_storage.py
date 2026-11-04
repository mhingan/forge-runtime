from forge_runtime.models import RunRecord, RuntimeEvent
from forge_runtime.storage import SQLiteStore


def test_persists_run_and_events(tmp_path):
    store = SQLiteStore(f"sqlite:///{tmp_path / 'state.db'}")
    run = RunRecord(goal="persist")
    store.save_run(run)
    store.add_event(RuntimeEvent(run_id=run.id, event_type="test", message="hello"))
    saved = store.get_run(run.id)
    assert saved is not None
    assert saved["goal"] == "persist"
    assert len(saved["events"]) == 1
