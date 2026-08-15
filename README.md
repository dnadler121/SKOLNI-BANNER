# BANNER v14 – přímý HTML rozvrh

v14 nechává funkční GUI z v10, ale zdroj dat mění z PDF na HTML stránky `KRO003_VypisTridy.aspx`.

## Co je nové
- bez Playwrightu a bez Chromia
- bez PDF parseru
- parser čte přímo `CCADynamicCalendarTable`
- u každé hodiny používá tooltip s údaji Učitel / Učebna / Den (vyuč. hodina)
- dělené hodiny se seskupují podle stejného dne a čísla hodiny
- školní akce se zpracují samostatně
- načítá se pouze aktuální týden

## Spuštění
```bash
pip install -r requirements.txt
cp .env.example .env
# doplň SKOLAONLINE_USER a SKOLAONLINE_PASSWORD
python app.py
```

## Test parseru
Na stránce rozvrhu je tlačítko **Test parseru (prosinec)**. To používá uložené skutečné HTML BB1A a ověřuje, že parser i GUI fungují nezávisle na přihlášení.

## Důležitá poznámka
Veřejná přihlašovací vrstva Školy Online je chráněna BotStopperem. v14 zkouší čisté serverové přihlášení přes `requests.Session()`. Pokud jej BotStopper zablokuje, aplikace to oznámí a neotevírá žádné okno prohlížeče. Samotný HTML parser je už ověřitelný tlačítkem testu.

## Instagram nástěnka (v19)
Tlačítko Instagram načítá na pozadí posledních 40 příspěvků profilu `@sssaskv`, uloží jejich obrázky lokálně a zobrazuje je po 12 (3×4) každých 10 sekund pořád dokola. Fotografie nejsou klikací a z obrazovky vede pouze tlačítko ZPĚT. Cache se obnovuje přibližně jednou za hodinu. Pokud nejsou nastaveny `INSTAGRAM_USER` a `INSTAGRAM_PASSWORD`, použijí se `SKOLAONLINE_USER` a `SKOLAONLINE_PASSWORD`.
