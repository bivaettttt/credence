import re
from pathlib import Path
from subprocess import check_output
from xml.etree import ElementTree

tracked = check_output(["git", "ls-files", "-z"]).decode().split("\0")
signature = re.compile(
    rb"gh[pous]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)
for filename in filter(None, tracked):
    path = Path(filename)
    data = path.read_bytes()
    if signature.search(data) or path.name == ".env":
        raise SystemExit(f"Suspected credential: {path}")
    if path.suffix == ".md":
        for link in re.findall(r"\]\(([^)]+)\)", data.decode()):
            target = link.partition("#")[0]
            if target and "://" not in target and not (path.parent / target).exists():
                raise SystemExit(f"Broken link in {path}: {link}")
    if path.suffix == ".bpmn":
        root = ElementTree.fromstring(data)
        ids = [node.get("id") for node in root.iter() if node.get("id")]
        if len(ids) != len(set(ids)):
            raise SystemExit(f"Duplicate IDs in {path}")
        for node in root.iter():
            for ref in ("sourceRef", "targetRef", "bpmnElement"):
                if ref in node.attrib and node.attrib[ref] not in ids:
                    raise SystemExit(f"Broken BPMN reference: {path}")
