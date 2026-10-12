"""Turn the end of failed CI logs into GitHub annotations, so the failure reason is visible on the run page
(and through the API) without opening the raw logs.   python tools/ci_annotate.py file1.txt file2.txt ..."""
import re
import sys
from pathlib import Path

KEY = re.compile(r"(FAILED|ERROR|Error|error:|What went wrong|Exception|Traceback|assert|> Task .*FAILED|BUILD FAILED)")

for name in sys.argv[1:]:
    p = Path(name)
    if not p.exists():
        continue
    lines = p.read_text(errors="replace").splitlines()
    key = [ln for ln in lines if KEY.search(ln)][-40:]
    tail = lines[-60:]
    for title, chunk in (("key lines", key), ("last lines", tail)):
        if chunk:
            msg = "\n".join(chunk)[-20000:]
            msg = msg.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
            print(f"::error title={p.name} ({title})::{msg}")
