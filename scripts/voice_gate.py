#!/usr/bin/env python3
"""Voice gate for foxlessons.com (2026-09-19).

Encodes the greppable half of ../VOICE.md and of the estate catalog at
~/Desktop/site-ops/AI-TELLS-2026.md (BASE-VOICE rule 9). The other half is a
read: the conceptual-agency ban, the promise, the instrument truth table, the
stranger's read-aloud (Layer 7).

HITS fail the gate (exit 1): em dashes and exclamation marks in copy,
"quietly", the ratified kill list, the ADHD rails (with the sanctioned
teacher-not-therapist and MT-BC referral sentences exempt), the dead promise,
names that never publish, the 2023-26 tell lexicon, sincerity markers and
candor flags.

NOTES print for the read and never fail: uncontracted forms on a first-person
surface, paragraphs closing on a fragment of three words or fewer.

Scans _src/pages/**/sections/*.html (HTML comments stripped), every
content.yaml, config.json titles and descriptions, the partials and the llms
template. Run: python3 scripts/voice_gate.py
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "_src"
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

HITS = [
    ("em dash", re.compile("—"), "no em dashes in site copy (VOICE 1)"),
    ("exclamation mark", re.compile(r"!(?![\[=])"), "no exclamation marks (VOICE 1)"),
    ("quietly", re.compile(r"\bquietly\b", re.I), "the word never publishes"),
    ("kill list", re.compile(r"unlock your potential|musical journey|\bjourney\b|passion for music|nurturing environment|all skill levels|\boutcall\b|holistically", re.I),
     "ratified kill list (VOICE 2)"),
    ("ADHD rails", re.compile(r"special needs|suffers? from|\b(high|low)[- ]functioning\b|ADHD superpower|differently[- ]abled|for all abilities", re.I),
     "ADHD rails (VOICE 2)"),
    ("ADHD rails", re.compile(r"\b(treatment|therapeutic|intervention|cure)\b", re.I), "ADHD rails: clinical diction never publishes"),
    ("dead promise", re.compile(r"real song in (the|your) first lesson|First 90 Days|three-song program", re.I), "dead promise (VOICE 3)"),
    ("jam rails", re.compile(r"on stage with you", re.I), "say I'll be there (VOICE 4)"),
    ("never publish", re.compile(r"Jim Zartman|\bSuno\b|jazz theory under everything|bass was more cumbersome", re.I), "VOICE 5 and 7"),
    ("tell lexicon", re.compile(
        r"\b(delve|tapestry|testament|realm|seamless|holistic|multifaceted|leverage|synergy|"
        r"elevate|unlock|supercharge|load-bearing|full stop|belt and suspenders|smoking gun|"
        r"the unlock|does the heavy lifting|chef's kiss|at its core|it's worth noting|"
        r"worth stating plainly|put differently|the version of|the version where|"
        r"the shape of|the work is the work)\b", re.I), "AI-TELLS Layer 1 and 2"),
    ("sincerity marker", re.compile(r"\b(genuinely|truly)\b|\bI mean that\b|\bI'm upfront\b", re.I), "prose that vouches for itself"),
    ("candor flag", re.compile(r"\b(honestly|candidly|full disclosure|the honest answer|honest gap|honest version|"
                               r"straight answer|if I'm honest|full honesty|the honest scope|the honest fork|"
                               r"an honest answer|honest alternative|honest comparison|honest training)\b", re.I),
     "state the thing without a label"),
]
# "clinical" is on the rails; the sanctioned exceptions name clinical goals
# while pointing to a therapist, and the music-therapy guide describes the
# other side of the line.
# Proper-noun titles on the cover walls that would otherwise trip a check.
TITLES_OK = ("Stand!", "Tapestry")
CLINICAL = re.compile(r"\bclinical\b", re.I)
CLINICAL_OK = re.compile(r"therap|goals|MT-BC|clinician", re.I)

NOTES = [
    ("uncontracted", re.compile(r"\b(it|that|there|here) is\b|\b(they|we|you) (are|will)\b|"
                                r"\bI (am|will|have|would)\b|\b(do|does|did|is|are|was|were|"
                                r"can|could|would|should|will|have|has|had) not\b")),
]
SHORT_CLOSER = re.compile(r"(?:^|\.\s+)([A-Z][^.!?]{0,20}[.!?])\s*$")


def texts():
    for p in sorted(SRC.glob("pages/**/sections/*.html")):
        yield p, COMMENT.sub("", p.read_text())
    for p in sorted(SRC.glob("pages/**/content.yaml")):
        yield p, p.read_text()
    for p in sorted(SRC.glob("pages/**/config.json")):
        cfg = json.loads(p.read_text())
        yield p, "\n".join(str(cfg.get(k, "")) for k in ("title", "seo_title", "meta_description"))
    for p in (SRC / "llms-template.txt", SRC / "partials" / "header.html", SRC / "partials" / "footer.html"):
        if p.exists():
            yield p, p.read_text()


def strip_markup(text):
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return text.replace("&rsquo;", "'").replace("&#x27;", "'").replace("&amp;", "&")


def main():
    hits, notes = [], []
    for path, raw in texts():
        rel = path.relative_to(ROOT)
        text = strip_markup(raw)
        if path.suffix == ".yaml":
            text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        for i, line in enumerate(text.splitlines(), 1):
            scan = line
            for t in TITLES_OK:
                scan = scan.replace(t, "")
            for label, pat, fix in HITS:
                if pat.search(scan):
                    hits.append((rel, i, label, fix, line.strip()[:100]))
            if CLINICAL.search(line) and not CLINICAL_OK.search(line):
                hits.append((rel, i, "ADHD rails", "clinical only inside the therapist disclaimer or referral", line.strip()[:100]))
            for label, pat in NOTES:
                found = pat.findall(line)
                if found:
                    notes.append((rel, i, label, len(found), line.strip()[:100]))
        for para in re.split(r"\n\s*\n", text):
            para = " ".join(para.split())
            m = SHORT_CLOSER.search(para)
            if m and len(m.group(1).split()) <= 3 and len(para) > 120:
                notes.append((rel, 0, "short closer", 1, m.group(1)))
    if notes:
        print("Notes (a read, never a failure):")
        for rel, i, label, n, line in notes:
            print(f"  {rel}{':' + str(i) if i else ''}  {label} x{n}: {line}")
    if hits:
        print("\nHITS:")
        for rel, i, label, fix, line in hits:
            print(f"  {rel}:{i}  [{label}] {line}\n      -> {fix}")
        print(f"\n{len(hits)} hit(s).")
        return 1
    print("\nGate clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
