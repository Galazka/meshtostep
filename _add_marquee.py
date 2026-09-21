# -*- coding: utf-8 -*-
"""Wstawia pasek statusu farmy (prt-marquee) do podstron po zamknieciu topbara."""
import os

SNIP = """
<!-- PASEK STATUSU FARMY -->
<div class="prt-marquee">
  <div class="prt-marquee-in">
    <div class="mq-l">
      <span class="prt-mq-pip">Farma Gda\u0144sk Osowa: 12/12 ONLINE</span>
      <span class="sep hide-s">/</span><span class="hide-s">Czas cyklu: SLA 48h</span>
      <span class="sep hide-s">/</span><span class="hide-s">Kalibracja sto\u0142\u00f3w LiDAR 7&micro;m</span>
    </div>
    <div class="mq-r">
      <span class="hide-s">Wycena STL/3MF w 30 s</span>
      <span class="sep hide-s">|</span>
      <b>InPost Paczkomat 24/7 &middot; BLIK</b>
    </div>
  </div>
</div>
"""

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
files = ["order.html", "konto.html", "blog.html", "kontakt.html", "payment.html"]

for name in files:
    path = os.path.join(base, name)
    with open(path, "rb") as fh:
        data = fh.read()
    if b"prt-marquee" in data:
        print(name, "SKIP (juz jest)")
        continue
    i = data.find(b"prt-topbar")
    if i < 0:
        print(name, "SKIP (brak topbara)")
        continue
    j = data.find(b"</nav>", i)
    if j < 0:
        print(name, "SKIP (brak </nav>)")
        continue
    j += len(b"</nav>")
    snip = b"\r\n" + SNIP.strip().encode("utf-8").replace(b"\n", b"\r\n") + b"\r\n"
    data = data[:j] + snip + data[j:]
    with open(path, "wb") as fh:
        fh.write(data)
    print(name, "OK")
