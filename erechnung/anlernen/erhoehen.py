"""Erhöhter Aufruf per UAC (ShellExecuteExW, Verb runas) und die Prüfungen, die der erhöhte Prozess selbst macht."""
import ctypes, json, os, subprocess, sys
from ctypes import wintypes
from pathlib import Path
from ..bereiche import NAME
from .verwalten import _kein_link
ABGEBROCHEN = 1223          # ERROR_CANCELLED: Benutzer hat die UAC-Abfrage abgelehnt
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
    if not shell32.ShellExecuteExW(ctypes.byref(sei)):
        fehler = ctypes.get_last_error()
        if fehler == ABGEBROCHEN:
            return -1
        raise RuntimeError(f"Administrator-Aufruf nicht startbar (Windows-Fehler {fehler})")
    if not sei.hProcess:
        raise RuntimeError("Administrator-Aufruf ohne Prozess")
    try:
        kernel32.WaitForSingleObject(sei.hProcess, 0xFFFFFFFF)
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(code))
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
def pruefe_konfig(konfig: Path, erlaubt: Path) -> Path:
    """Erhöhter Lauf: nur die konfig.json des Programmordners (sonst lenkt der Benutzer Schreibziele um)."""
    if os.path.normcase(konfig.resolve()) != os.path.normcase(erlaubt.resolve()):
        raise ValueError("--konfig ist nicht die konfig.json im Programmordner")
    return erlaubt
def schreibe_ergebnis(datei: Path, ergebnis: dict) -> None:
    """Ergebnis für den unerhöhten Server: sein frischer Ordner (keine Verknüpfung), Datei neu und exklusiv."""
    _kein_link(datei.parent)
    with open(datei, "x", encoding="utf-8") as f:     # existiert schon → FileExistsError
        json.dump(ergebnis, f, ensure_ascii=False)
def pruefe_entwurf_pfad(entwurf: Path) -> Path:
    """Erhöhter Lauf: nur `<Anlern-Daten>\\entwuerfe\\<name>`; der Pfad muss bleiben (bei Freigabe durch ein anderes
    Admin-Konto zeigt %LOCALAPPDATA% auf dessen Profil), gelesen wird ohnehin nur eine geprüfte Kopie (verwalten)."""
    if not (entwurf.is_absolute() and NAME.fullmatch(entwurf.name) and entwurf.parent.name == "entwuerfe"
            and entwurf.parent.parent.name == "anlernen"):
        raise ValueError("Entwurf liegt nicht im Anlern-Ordner")
    return entwurf
