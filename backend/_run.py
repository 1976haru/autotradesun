import subprocess
import sys
import xml.etree.ElementTree as ET

subprocess.run(
    [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
     "--junit-xml=_junit.xml", "-q", "-o", "junit_logging=no"],
    capture_output=True,
)
root = ET.parse("_junit.xml").getroot()
suite = root if root.tag == "testsuite" else root.find("testsuite")
total = int(suite.get("tests", 0))
fails = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
bad = []
for tc in suite.iter("testcase"):
    for kind in ("failure", "error"):
        el = tc.find(kind)
        if el is not None:
            msg = (el.get("message") or "").splitlines()[0][:90]
            bad.append(f"{tc.get('name')}::{msg}")
out = f"TOTAL={total} FAILS={fails}\n" + "\n".join(bad)
open("_verdict.txt", "w", encoding="utf-8").write(out)
print("WROTE")
