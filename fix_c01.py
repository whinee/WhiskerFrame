with open("docs/dev/spec-interview/contradictions.md", "r") as f:
    text = f.read()

# Update Table
text = text.replace("| C-01 | BLOCKER  | OPEN   | Cess art terms vs. open-sourcing everything | A.12, 1.08, docs/README.md |",
                    "| C-01 | BLOCKER  | RESOLVED | Cess art terms vs. open-sourcing everything | A.12, 1.08, docs/README.md |")
text = text.replace("| C-02 | MEDIUM   | OPEN   | OTG Power &amp; Data constraints            | A.13, topology             |",
                    "| C-02 | MEDIUM   | RESOLVED | OTG Power &amp; Data constraints            | A.13, topology             |")

# Move C-01 and C-02 to Resolved block
import re
c01_match = re.search(r'(### C-01.*?)(?=### C-02)', text, re.DOTALL)
c02_match = re.search(r'(### C-02.*?)(?=## Resolved)', text, re.DOTALL)

if c01_match and c02_match:
    c01 = c01_match.group(1).replace('OPEN', 'RESOLVED')
    c02 = c02_match.group(1).replace('OPEN', 'RESOLVED')
    text = text.replace(c01_match.group(1), "")
    text = text.replace(c02_match.group(1), "")
    text += f"{c01}\n{c02}\n"

with open("docs/dev/spec-interview/contradictions.md", "w") as f:
    f.write(text)

