import json
from pathlib import Path
from ea_optimizer_lab.auto_runner import _status

def test_auto_status_is_atomic_readable_json(tmp_path: Path):
    path=tmp_path/"status.json"; _status(path,"train","running",current=2)
    data=json.loads(path.read_text(encoding="utf-8"))
    assert data["stage"]=="train" and data["current"]==2
