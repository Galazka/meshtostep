"""Walidator CSS w order.html: niezamkniete klamry cicho uniczawiaja caly blok
po danym miejscu (przegladarka ignoruje reguly w srodku niezamknietego @media).
Uzycie: python checkcss.py [plik.html]"""
import io, sys
p = sys.argv[1] if len(sys.argv) > 1 else "frontend/order.html"
s = io.open(p, encoding="utf-8").read()
k, j = s.find("<style"), s.find("</style>")
assert k >= 0 and j > k, "nie znaleziono <style>...</style>"
css = s[s.find(">", k) + 1:j]
d = 0
for ch in css:
    if ch == "{": d += 1
    elif ch == "}": d -= 1
assert d == 0, f"CSS niezbalansowany: depth={d} (klamra otwarta/zamknieta w innym miejscu)"
print(f"CSS OK ({len(css)} znakow, klamry zbalansowane)")
