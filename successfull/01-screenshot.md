# CMD 01: Screenshot (Full Screen)

**Befehl:**

```bash
screencapture -x /tmp/s1.png
```

**Beschreibung:** Erstellt einen Screenshot des gesamten Bildschirms (alle Monitore).
Die `-x` Flag verhindert den Kamera-Sound. Das Bild wird als PNG gespeichert.

**Warum Full-Screen:** Chrome-Fenster-spezifische Screenshots (`-l windowID` oder `-R x,y,w,h`)
brauchen macOS Screen Recording Permission. Full-Screen (`-x`) funktioniert immer.

**Abhängigkeiten:** macOS `screencapture` (vorinstalliert)

**Erfolgskriterium:** Datei existiert mit >0 Bytes

**Output:** `/tmp/s1.png` — Screenshot für nächsten Vision-Schritt
