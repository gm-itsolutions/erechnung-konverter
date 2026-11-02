"""Prüfung jeder E-Rechnung mit Mustang-CLI (XSD + EN16931-Schematron), Spezifikation Abschnitt 3.4."""
import os
import re
import shutil
import subprocess
from pathlib import Path
from lxml import etree

WURZEL = Path(__file__).resolve().parents[2]   # im ZIP: app\erechnung → ..\.. (java\, mustang\)
FRIST = 60          # Sekunden je Rechnung
MELDUNGEN = 10      # höchstens so viele Meldungen in die Fehlerdatei
# C1-Compiler und Serial-GC: Start 2,5 statt 4 s, 130 statt 200 MB (gemessen 02.11.2026, Mustang 2.26.0)
JVM = ["-Xmx512m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1"]


def mustang() -> list[str] | None:
    """Aufruf ohne Quelle: mitgeliefertes java\\bin\\java.exe + mustang\\Mustang-CLI-*.jar,
    sonst java aus PATH und Jar aus MUSTANG_JAR (Entwicklung, CI). None, wenn eins fehlt."""
    jars = sorted((WURZEL / "mustang").glob("Mustang-CLI-*.jar"))
    jar = jars[-1] if jars else (Path(os.environ["MUSTANG_JAR"]) if os.environ.get("MUSTANG_JAR") else None)
    exe = WURZEL / "java" / "bin" / "java.exe"
    java = str(exe) if exe.is_file() else shutil.which("java")
    if not (jar and jar.is_file() and java):
        return None
    return [java, *JVM, "-jar", str(jar), "--no-notices", "--action", "validate", "--source"]


def _meldung(text: str) -> str:
    """„[BR-CO-15]-Text [ID BR-CO-15] from /xslt/…)“ → „BR-CO-15: Text“; andere Meldungen gekürzt."""
    text = " ".join(text.split())
    m = re.match(r"\[([^\]]+)\]-(.*?)(?: \[ID [^\]]*\] from .*)?$", text)
    return f"{m[1]}: {m[2]}" if m else text[:300]


def pruefe(quelle: Path, aufruf: list[str]) -> str:
    """Mustang auf `quelle` (CII-XML). Gültig → Kurzbericht fürs Log; sonst ValueError mit Regel-IDs und Texten."""
    try:
        p = subprocess.run([*aufruf, str(quelle)], capture_output=True, timeout=FRIST,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise ValueError(f"Mustang-Prüfung: Frist {FRIST} s überschritten, keine E-Rechnung abgelegt") from None
    except OSError as e:
        raise ValueError(f"Mustang nicht startbar: {e}") from None
    aus = p.stdout
    start = aus.find(b"<validation")
    try:
        wurzel = etree.fromstring(aus[start:], etree.XMLParser(resolve_entities=False, no_network=True)) if start >= 0 else None
    except etree.XMLSyntaxError:
        wurzel = None
    if wurzel is None:
        rest = (p.stderr or aus).decode("utf-8", "replace").strip()[-300:]
        raise ValueError(f"Mustang-Prüfung ohne Bericht (Code {p.returncode}): {rest}")
    status = wurzel.xpath("string(summary/@status)")
    if status == "valid" and p.returncode == 0:
        x = wurzel.find("xml")
        return (f"{status}, Profil {x.findtext('info/profile', '?')}, {x.findtext('info/rules/fired', '?')} Regeln, "
                f"{x.findtext('info/rules/failed', '?')} verletzt, Mustang {x.xpath('string(info/validator/@version)')}, "
                f"{x.findtext('info/duration', '?')} ms")
    meldungen = [_meldung(e.text or "") for e in wurzel.iter("error")]
    zeilen = meldungen[:MELDUNGEN] + ([f"… und {len(meldungen) - MELDUNGEN} weitere"] if len(meldungen) > MELDUNGEN else [])
    raise ValueError(f"E-Rechnung laut Mustang ungültig (Status {status or '?'}, Code {p.returncode}):\n" + "\n".join(zeilen))
