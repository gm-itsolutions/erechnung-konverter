"""Erhöhter Aufruf per UAC (ShellExecuteExW, Verb runas) und die Prüfungen, die der erhöhte Prozess selbst macht."""
import ctypes, json, os, re, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path
from ..bereiche import NAME
from .verwalten import _kein_link
ABGEBROCHEN = 1223          # ERROR_CANCELLED: Benutzer hat die UAC-Abfrage abgelehnt
WARTEN_MS, WAIT_TIMEOUT = 10 * 60 * 1000, 0x102
ERGEBNIS_ID, ERGEBNISSE, AUFHEBEN = re.compile(r"[0-9a-f]{16}"), "ergebnisse", 24 * 3600
class _SEI(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD),
                ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
def _windows() -> bool:
    return os.name == "nt"
def als_admin(argumente: list[str]) -> int:
    """python.exe neben der laufenden pythonw.exe erhöht starten, warten, Exit-Code; UAC abgelehnt → -1."""
    if not _windows():
        raise RuntimeError("UAC gibt es nur unter Windows")
    ordner = os.path.dirname(sys.executable)
    python = os.path.join(ordner, "python.exe")      # nicht pythonw: Exit-Code zuverlässig
    sei = _SEI(cbSize=ctypes.sizeof(_SEI), fMask=0x00000040, lpVerb="runas", lpFile=python,   # SEE_MASK_NOCLOSEPROCESS
               lpParameters=subprocess.list2cmdline(argumente), lpDirectory=ordner, nShow=0)  # Arbeitsordner im Programmordner
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes, shell32.ShellExecuteExW.restype = (ctypes.POINTER(_SEI),), wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes, kernel32.WaitForSingleObject.restype = (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD
    kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes, kernel32.CloseHandle.restype = (wintypes.HANDLE,), wintypes.BOOL
    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        fehler = ctypes.get_last_error()
        if fehler == ABGEBROCHEN:
            return -1
        raise RuntimeError(f"Administrator-Aufruf nicht startbar (Windows-Fehler {fehler})")
    if not sei.hProcess:
        raise RuntimeError("Administrator-Aufruf ohne Prozess")
    try:
        if kernel32.WaitForSingleObject(sei.hProcess, WARTEN_MS) == WAIT_TIMEOUT:
            raise RuntimeError("UAC-Abfrage nicht beantwortet")
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(code)):
            raise RuntimeError(f"Exit-Code nicht lesbar (Windows-Fehler {ctypes.get_last_error()})")
        return code.value
    finally:
        kernel32.CloseHandle(sei.hProcess)

def programm_konfig() -> Path:
    """konfig.json im Programmordner, abgeleitet aus der Lage des laufenden Pakets (…\\GM-IT\\erechnung-konverter\\
    versionen\\<v>\\app\\erechnung oder …\\aktuell\\app\\erechnung), nie aus einer Eingabe des Benutzers."""
    for o in Path(__file__).resolve().parents:
        if o.name.lower() == "erechnung-konverter" and o.parent.name.lower() == "gm-it":
            return o / "konfig.json"
    raise ValueError("Programmordner GM-IT\\erechnung-konverter nicht gefunden")
def _kein_unc(p: Path) -> None:
    r"""UNC- und Gerätepfade (\\host\…, \\?\UNC\…, \\.\…) vor jedem Zugriff ablehnen: sonst meldet sich der
    Admin-Prozess an einem fremden Rechner an (NTLM)."""
    if str(p).replace("/", "\\").startswith("\\\\"):
        raise ValueError(f"Netzwerk- oder Gerätepfad nicht erlaubt: {p}")
def pruefe_konfig(konfig: Path, erlaubt: Path) -> Path:
    """Erhöhter Lauf: nur die konfig.json des Programmordners (sonst lenkt der Benutzer Schreibziele um).
    Reiner Pfadvergleich ohne Dateizugriff; zurück kommt der erlaubte Pfad, nie der übergebene."""
    _kein_unc(konfig)
    if os.path.normcase(os.path.abspath(konfig)) != os.path.normcase(os.path.abspath(erlaubt)):
        raise ValueError("--konfig ist nicht die konfig.json im Programmordner")
    return erlaubt
def ergebnis_datei(programm: Path, eid: str) -> Path:
    """Ergebnis des erhöhten Laufs: `<Programmordner>\\ergebnisse\\<id>.json` (Users: nur Lesen)."""
    if not isinstance(eid, str) or not ERGEBNIS_ID.fullmatch(eid):
        raise ValueError("Ergebnis-ID ungültig")
    return programm / ERGEBNISSE / f"{eid}.json"
def schreibe_ergebnis(programm: Path, eid: str, ergebnis: dict) -> None:
    """Erhöhter Lauf: Ordner selbst anlegen, ohne Verknüpfung bis zum Programmordner, exklusiv schreiben,
    Ergebnisse älter als einen Tag wegräumen (der unerhöhte Server darf dort nur lesen)."""
    datei = ergebnis_datei(programm, eid)
    datei.parent.mkdir(exist_ok=True)
    for o in (datei.parent, programm):
        _kein_link(o)
    grenze = time.time() - AUFHEBEN
    for alt in datei.parent.glob("*.json"):
        try:
            if os.lstat(alt).st_mtime < grenze:
                alt.unlink()
        except OSError:
            pass
    with open(datei, "x", encoding="utf-8") as f:     # existiert schon → FileExistsError
        json.dump(ergebnis, f, ensure_ascii=False)
def benutzer_name(roh: str) -> str:
    """Benutzername für Log und Protokoll: nur druckbare Zeichen (kein Zeilenumbruch), höchstens 64."""
    return "".join(c for c in roh if c.isprintable())[:64]
def pruefe_entwurf_pfad(entwurf: Path) -> Path:
    """Erhöhter Lauf: nur `<Anlern-Daten>\\entwuerfe\\<name>`; der Pfad muss bleiben (bei Freigabe durch ein anderes
    Admin-Konto zeigt %LOCALAPPDATA% auf dessen Profil), gelesen wird ohnehin nur eine geprüfte Kopie (verwalten)."""
    _kein_unc(entwurf)
    if not (entwurf.is_absolute() and NAME.fullmatch(entwurf.name) and entwurf.parent.name == "entwuerfe"
            and entwurf.parent.parent.name == "anlernen"):
        raise ValueError("Entwurf liegt nicht im Anlern-Ordner")
    return entwurf
