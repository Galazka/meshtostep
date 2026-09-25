#!/usr/bin/env python3
"""3dfile.link — streszczenie ostatnich N raportów dziennych.

Skrypt czyta outputy joba cron 3dfile-dzienny z ~/AppData/Local/hermes/cron/output/<job_id>/
i skleja je w jeden przegląd trendów. Służy na czacie: 'podsumuj raporty z 3 dni'.

Użycie:  python ops/3dfile_summary.py [N]   (domyślnie 3 ostatnie raporty)
Wyjście: TREŚĆ_ORIGINALNYCH raportów (sklejona) — NIE lokalizuj/nie tłumacz liczb.
"""
import glob
import os
import sys
from datetime import datetime

CRON_OUT = r"C:/Users/galaz/AppData/Local/hermes/cron/output/7eb76fcaf3e7"


def collect_job_outputs(n: int) -> list[tuple[str, str]]:
    """Zwraca listę (data-piękna, treść) dla ostatnich n plików .md w kolejności chronologicznej."""
    files = sorted(glob.glob(os.path.join(CRON_OUT, "*.md")))
    res = []
    for f in files[-n:]:
        base = os.path.basename(f)  # 2026-09-25_17-41-02.md
        try:
            d = datetime.strptime(base, "%Y-%m-%d_%H-%M-%S.md")
            label = d.strftime("%d.%m.%Y %H:%M")
        except Exception:
            label = base
        with open(f, encoding="utf-8") as fh:
            res.append((label, fh.read()))
    return res


def strip_header(text: str) -> str:
    """Odcina nagłówek Hermesa (# Cron Job ...) — zostaje sam raport od '🦞'."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("🦞"):
            return "\n".join(lines[i:])
    return text


def main() -> int:
    n = 3
    if len(sys.argv) > 1:
        try:
            n = int(sys.argv[1])
        except ValueError:
            n = 3

    items = collect_job_outputs(n)
    if not items:
        print("Brak raportów w", CRON_OUT)
        return 1

    out = []
    # nagłówek projektu (raz)
    example = strip_header(items[-1][1]) if items else ""
    head = example.splitlines()[0] if example else "3dfile.link"
    out.append(head.replace(" — raport dzienny", " — podsumowanie") + " (agregat)")

    for label, text in items:
        body = strip_header(text)
        # pominąć linię ze znacznikiem czasu w raporcie (duplikat labelki)
        body_lines = [l for l in body.splitlines() if not l.startswith("🦞")]
        out.append(f"\n── [{label}] ──")
        out.extend(body_lines)

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
