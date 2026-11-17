# SKRATCHA 1.0.0 – by JJ DA PLUG

Scratch-Plattenspieler für die MPC (offizielles MPC Plugin SDK), im Stil eines klassischen Direct-Drive-DJ-Decks.
Instrument-Plugin: Es spielt eine „Platte“ (WAV) ab, die du mit dem Touchstrip, dem Plattenteller auf dem Bildschirm
oder einem Q-Link bewegst.

## Auf der MPC einrichten
1. MPC OS 3.10.1 oder neuer. Preferences → Enhancements (Beta) → **Enable Enhancements** und **External Plugin Support** an.
2. Neuer Track → Plugin → External Plugins → **SKRATCHA**.
3. Touchstrip auf **PITCH BEND** stellen (Touch-Strip-Taste halten und PITCH BEND wählen). Relative Mode: aus.
4. Touchstrip berühren = Hand auf der Platte. Bewegen = scratchen. Loslassen = der Motor übernimmt.

## Pads (ab PAD BASE, Standard C1 = 36)
| Pad | Funktion |
|---|---|
| 1 | START/STOP (Motor mit Anlauf- und Bremszeit) |
| 2 | CUT – Fader zu, solange gehalten (Transformer/Chirp) |
| 3 | HOLD – Hand auf der Platte, solange gehalten (Platte halten, loslassen auf den Beat) |
| 4 | CUE – zum Cue-Punkt springen |
| 5 | SET CUE – setzt den Cue; gehalten + Hot-Cue-Pad = Hot Cue speichern |
| 6 | REVERSE |
| 7 | 33/45 |
| 8 | FADER an/aus |
| 9–16 | HOT CUE 1–8 (leer: speichern, sonst springen) |

Weil der Touchstrip Pitch Bend sendet, nimmt die MPC deine Scratches als MIDI auf und spielt sie wieder ab.

## Eigene Platten (WAV)
- In `MPC Documents/SKRATCHA/` auf einem Laufwerk, oder in den Ordner `My Samples` im Plugin-Ordner.
- SETUP → RESCAN liest die Ordner neu. Bis 64 Dateien, je bis 90 s (längere werden gekürzt).
- Mitgeliefert (selbst synthetisiert, frei): AHH, OOH WAH, STAB, TONE 1K, BREAK 92, BASS DROP.

## Reiter
- **DECK**: Plattenteller (drehendes Label mit JF-Logo und Cue-Sticker, Strobe-Ring), START/STOP, 33/45, Pitch-Fader,
  Plattenwahl (antippen und wischen), SMOOTH, RANGE, CATCH, LEVEL, FADER, REVERSE, Touchstrip-Anzeige.
- **SETUP**: Start-/Bremszeit, Pitch-Bereich (8/16/50 %), 1X/LOOP, Strip-Richtung, Loslassen (CENTER/TIMEOUT), Cut-Kurve,
  Crackle, Catch, Pad-Basis, RESCAN, SCRATCH-Balken (für den Touchstrip im Q-LINK-Modus).
- **INFO**: JF-Logo, Creator JJ DA PLUG, Kurzanleitung.

## Technik
- Touchstrip-Werte (14 Bit) werden sample-genau verarbeitet. Zwischen zwei Werten gleitet das Ziel linear über den gemessenen
  Meldeabstand, danach folgt die Platte einer kritisch gedämpften Feder (SMOOTH, Standard 3 ms). Ergebnis im Test:
  keine messbare Restwelligkeit bei der Meldefrequenz, Tonhöhe folgt der Hand auf ±2 Cent.
- Mipmap-Wiedergabe (6 Stufen bis 32-fach) gegen Aliasing bei schnellen Scratches.
- Laden, Aufräumen und Live-Anzeige (Plattenwinkel ~30×/s, Strobe, LEDs) laufen in einem eigenen Thread, nie im Audio-Thread.
- CPU (PC, nur zur Orientierung): ~0,1–0,3 % pro Block. Auf der MPC noch messen.

## Noch nicht auf der MPC getestet
- Ob die MPC beim Loslassen des Strips im PITCH-BEND-Modus auf 0 (Mitte) zurückspringt. Falls nicht: SETUP → LET GO WHEN = TIMEOUT.
- Welche Noten die Pads auf einem Plugin-Track senden (Standard angenommen: ab C1 = 36; sonst PAD BASE = C#1 37).
- Ob die MPC das Drehen am Plattenteller auf dem Bildschirm (AbsoluteRotaryKnob) flüssig meldet.
- Wie flüssig die MPC die Live-Anzeige zeichnet.

## Bauen
```
python tools/build.py plugins/SKRATCHA
```
Ausgabe: `plugins/SKRATCHA/build/JJ DA PLUG - VST - SKRATCHA/` → in `VST2 Plugins` auf ein Laufwerk der MPC kopieren.
Der Skin liegt fertig in `skins/` (wird unverändert übernommen). Neu erzeugen: `tools/make_ui.py` im SKRATCHA-Werkzeugordner.

Lizenz: MIT. Schriften in den Grafiken: Rajdhani, Titillium Web (SIL OFL).
