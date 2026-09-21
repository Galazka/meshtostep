# -*- coding: utf-8 -*-
"""Dodaje mono oznaczenie 'Krok X z 4' w naglowkach krokow order.html."""
import io, os

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
path = os.path.join(base, "order.html")
with io.open(path, encoding="utf-8", newline="") as fh:
    s = fh.read()

pairs = [
    ('<h2><span class="n">1</span> Dodaj modele do druku</h2>',
     '<div class="krok">Krok 1 z 4</div>\n        <h2><span class="n">1</span> Dodaj modele do druku</h2>'),
    ('<h2><span class="n">2</span> Wybierz materia\u0142</h2>',
     '<div class="krok">Krok 2 z 4</div>\n        <h2><span class="n">2</span> Wybierz materia\u0142</h2>'),
    ('<h2><span class="n">3</span> Kolor i liczba kolor\u00f3w</h2>',
     '<div class="krok">Krok 3 z 4</div>\n        <h2><span class="n">3</span> Kolor i liczba kolor\u00f3w</h2>'),
    ('<h2><span class="n">4</span> Dane i dostawa</h2>',
     '<div class="krok">Krok 4 z 4</div>\n        <h2><span class="n">4</span> Dane i dostawa</h2>'),
]

changed = 0
for old, new in pairs:
    if old in s:
        s = s.replace(old, new, 1)
        changed += 1
    else:
        print("NIE ZNALEZIONO:", old[:60])

with io.open(path, "w", encoding="utf-8", newline="") as fh:
    fh.write(s)
print("zamienione:", changed, "/ 4")