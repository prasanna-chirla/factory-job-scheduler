"""Create and compare content manifests for repeatable generated inputs."""
import hashlib, json
from pathlib import Path

def build_manifest(root: Path, seed: int, counts: dict) -> dict:
    files=[]
    for path in sorted(root.rglob("*.csv")):
        if "ground_truth" not in path.parts and "output" not in path.parts:
            files.append({"path":path.relative_to(root).as_posix(),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    return {"seed":seed,"synthetic_only":True,"counts":counts,"files":files}

def same_inputs(first: dict, second: dict) -> bool:
    return first.get("counts")==second.get("counts") and first.get("files")==second.get("files")
