# 3dfile.link — Pełny audit + fixy (13.09.2026)

## Zrobione (subagents)
- [x] SyntaxError share pages — brak `}` w loadStlFallback
- [x] convert.js files undefined — null guard
- [x] Admin panel dane — None-guards + field name mismatches
- [x] Share links z nickiem — vanity URL `/u/{user}/{slug}`
- [x] Admin bulk-delete double JSON

## Do zrobienia (巡查)
### F1: Footer + "Jak to działa"
- [ ] Footer: pod logo dodać opis strony + hallo@3dfile.link
- [ ] "Jak to działa": sekcja z przykładami dla użytkowników
- [ ] EN tłumaczenia brakujących kluczy

### F2: Format selection przy pobieraniu
- [ ] Modal z wyborem: mesh (STL/3MF/OBJ) vs solid (STEP)
- [ ] Informacja o jakości/jakości konwersji

### F3: 3D viewer
- [ ] Share page: model "ścisnięty" — camera setup fix
- [ ] Stretching strony w prawo — overflow fix

### F4: Audit produkcji
- [ ] Curl test wszystkich endpointów
- [ ] Sprawdzenie CSS/JS loaded correctly
- [ ] Sprawdzenie i18n completeness
