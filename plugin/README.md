# SKRATCHA 2.0 – zwei Scratch-Plattenspieler für die MPC

Von **JJ DA PLUG**. Instrument-Plugin für die MPC Live III / XL (arm64) und die MPC Live / Live II / One (arm32), gebaut mit dem offiziellen MPC Plugin SDK.

SKRATCHA hat zwei Decks mit je acht Sample-Slots und einen Battle-Crossfader. Gescratcht wird mit dem Touch Strip. Dazu gibt es drei Plattenspieler-Stile und einen Scratch-Lehrer.

## Installation
1. Den Ordner `JJ DA PLUG - VST - SKRATCHA` in den Ordner `VST2 Plugins` auf einem Laufwerk kopieren (USB, SD oder SSD).
2. Voraussetzungen an der MPC:
   - MPC OS 3.10.1 oder neuer.
   - Preferences → Enhancements (Beta) → **Enable Enhancements** und **External Plugin Support** einschalten.
3. Einen Plugin-Track anlegen und SKRATCHA (JJ DA PLUG) wählen.
4. Den Touch Strip auf **PITCH BEND** stellen (SHIFT + Touch Strip).

**Zurück:** Den Ordner wieder löschen. Am System wird nichts verändert.

## Bedienung
- **DECK A / DECK B** (oben rechts oder Pad 12) wählt das aktive Deck. Nur das aktive Deck hört auf Strip und Bildschirm, und die Ansicht wechselt mit.
  - Der Wechsel passiert nur, wenn du ihn selbst auslöst.
  - Das andere Deck läuft weiter.
- **Touch Strip:** Berühren heißt Hand auf der Platte. Bewegen scratcht. Beim Loslassen fängt der Motor die Platte wieder (CATCH).
- **8 Slots pro Deck:**
  - Pads 1–8 entsprechen den Slot-Tasten auf dem Bildschirm. Die untere Reihe ist 1–4, die obere 5–8, wie auf den Pads.
  - Ein Slot legt sein Sample auf die Platte. Mit FIRE = PLAY (Standard) startet es sofort, mit CUE wartet es auf die Hand.
- **Crossfader:** Links ist Deck A, rechts Deck B. Q-Link 1 ist der Crossfader.
  - **CURVE** reicht von SMOOTH (weicher Übergang) bis RAZOR (offen nach 1,5 % Weg).
  - Das Kurvenbild zeigt, wie der Fader gerade arbeitet.
  - **CUT LAG** ist eine tote Zone am geschlossenen Ende, damit nichts durchblutet.
  - **HAMSTER** dreht die Seiten um.
- **CUT-Pad (Pad 10)** ist der schnellste Fader:
  - CUT CLOSE: Halten schließt das aktive Deck.
  - CUT OPEN: Das aktive Deck klingt nur, solange du hältst. Das ist ideal für Forwards, Chirps und Transformer.
  - **CUT SPEED** (SETUP) bestimmt, wie hart der Schnitt ist: 0,7, 3 oder 12 ms.
- **SIMPLE / ADVANCED** (Taste oben rechts):
  - In SIMPLE zeigt das Deck RANGE, CURVE, DECK-VOLUME und LEVEL.
  - In ADVANCED zeigt es SMOOTH, CATCH, CUT LAG und CRACKLE. SETUP zeigt dann alle Motor-Einstellungen.

### Pads (ab C1 = 36, in SETUP auf 37 umstellbar)
| Pad | Funktion | Pad | Funktion |
|---|---|---|---|
| 1–8 | Slot 1–8 des aktiven Decks | 13 | CUE (zurück zum Cue-Punkt) |
| 9 | START / STOP | 14 | SET CUE |
| 10 | CUT | 15 | REVERSE |
| 11 | HOLD (Hand auf der Platte) | 16 | 33 / 45 |
| 12 | DECK A ↔ B | | |

## Turntable-Stile (pro Deck)
Jeder Stil ändert den Klang, das Aussehen und das Spielgefühl.

| Stil | Motor | Platte unter der Hand | Gleichlauf | Klang |
|---|---|---|---|---|
| **DD SILBER** | Direktantrieb, normal | normal | sehr stabil | voll, sauber |
| **BATTLE** | sehr starkes Drehmoment (Start/Stopp blitzschnell, fängt sofort) | leicht, direkt | quarzstabil | voll, sauber |
| **RIEMEN 70ER** | schwacher Riemen (langer Anlauf, rutscht, fängt spät) | schwer, träge | leichtes Leiern | warm, etwas Rumpeln und Staub |

## BROWSER
1. Ordner wählen: über die Anzeige wischen oder Q-Link 1 drehen.
2. Datei wählen: über die Liste wischen oder Q-Link 2 drehen.
3. Mit **VORHÖREN** hörst du die Datei an.
4. Ziel-Deck wählen und auf einen **Slot tippen**. Die Datei wird geladen und liegt sofort auf der Platte.

Durchsucht werden:
- die eingebauten Samples,
- der Ordner `My Samples` im Plugin-Ordner,
- alle Laufwerke (USB, SD, SSD), bis 7 Ordner tief.

**NEU SUCHEN** liest die Laufwerke neu ein. Pro Slot werden höchstens 15 s geladen (WAV, mono oder stereo). Die Slot-Belegung wird im Projekt gespeichert.

## LERNEN – der Scratch-Lehrer
1. Eine Lektion wählen:
   1. BABY SCRATCH
   2. DRAG
   3. FORWARD
   4. CHIRP
   5. TRANSFORMER
   6. TEAR
2. **DEMO** drücken: Der Lehrer spielt die Bewegung zwei Takte lang auf dem aktiven Deck vor. Danach bist du automatisch dran.
3. **START**: Ein Takt wird vorgezählt, dann scratchst du.
   - Der grüne Punkt zeigt, wo deine Hand sein soll. Der orange Punkt zeigt, wo dein Finger ist.
   - **TON SOLL** und **TON IST** zeigen, ob das Deck gerade klingen soll und ob es klingt.
4. Nach jedem Takt bekommst du einen Tipp, zum Beispiel „FALSCHE RICHTUNG“, „MEHR BEWEGUNG“, „TON AN/AUS …“ oder „ERST MOTOR STOPPEN“.
5. Nach vier Takten gibt es 0–3 Sterne. Die beste Wertung wird gespeichert. Mit *** geht es zur nächsten Lektion.

Beim Start bereitet der Lehrer das Deck vor:
- Er stoppt den Motor.
- Er setzt CUT MODE passend zur Lektion.
- Er öffnet den Crossfader zum aktiven Deck.

Das Tempo stellst du mit BPM ein, den Klick schaltest du mit KLICK an und aus.

Die Presets BABY SCRATCH, DRAG, FORWARD, CHIRP, TRANSFORMER und TEAR stellen das Plugin für Anfänger passend ein und wählen gleich die passende Lektion.

## Presets
INIT, BABY SCRATCH, DRAG, FORWARD, CHIRP, TRANSFORMER, TEAR, BATTLE TIGHT, 45 HYPE, DUSTY BELT.

## Technik (ehrlich)
- **Hand:**
  - Eingaben kommen über Pitch Bend (14 Bit, sample-genau), Mod Wheel, Q-Link (SCRATCH), die Platte auf dem Bildschirm oder Pad HOLD.
  - Das Ziel gleitet über den gemessenen Meldeabstand. Danach glättet eine kritisch gedämpfte Feder die Bewegung, damit kein Zippern entsteht.
  - Am PC getestet: Die Tonhöhe folgt auf ±2 Cent. Aliasing bei 30-facher Geschwindigkeit liegt 30 dB unter dem Ton (6 Mipmap-Stufen).
- **Speicher:** bis 16 Samples à 15 s, als Mipmap etwa 2× so groß. Mit typischen kurzen Scratch-Samples sind das wenige MB.
- **Bildschirm:**
  - Die Live-Werte (Plattenwinkel, Strobe, LEDs, Lehrer) meldet ein Hintergrund-Thread etwa 30× pro Sekunde, nie der Audio-Thread.
  - Nur das sichtbare Deck dreht sich in der Anzeige.
- **Texte:** Die MPC zeigt höchstens 31 Zeichen pro Wert, deshalb sind die Tipps kurz.
- **Noch nicht auf der MPC getestet:** CPU-Last mit zwei Decks und Lehrer, flüssige Anzeige beim Deckwechsel, Laufwerkspfade der MPC für den Browser.

## Lizenzen
- Code: MIT.
- Samples: selbst synthetisiert.
- Grafiken: eigene Renderings mit dem JF-Logo des Erstellers.
- Schriften in den Bildern: Rajdhani und Titillium Web (SIL OFL).
