# SKRATCHA 2.1 – zwei Scratch-Plattenspieler für die MPC

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
### Die Pads = der Bildschirm (4 × 4)
Rechts auf dem DECK-Reiter liegen die 16 Pads genau so wie auf der MPC. Was du drückst, leuchtet auf dem Bildschirm mit. Tippen auf dem Bildschirm macht dasselbe wie das Pad.

| | Spalte 1 | Spalte 2 | Spalte 3 | Spalte 4 |
|---|---|---|---|---|
| **oben (13–16)** | DECK A | DECK B | REVERSE | SLIP |
| **(9–12)** | CUT (halten) | HOLD (Hand auf der Platte) | CUE (zurück zum Cue) | START / STOP |
| **(5–8)** | Sample 5 | Sample 6 | Sample 7 | Sample 8 |
| **unten (1–4)** | Sample 1 | Sample 2 | Sample 3 | Sample 4 |

- **Unten** liegen die Samples, **darüber** die Steuerung, **ganz oben** die Deck-Wahl.
- **HOLD + CUE** setzt den Cue-Punkt: Hand auf die Platte, die Stelle suchen, dann CUE tippen.
- **DECK A / DECK B** wählt das aktive Deck. Strip, Pads, Knöpfe und Anzeige gehören dann zu diesem Deck. Gewechselt wird nur, wenn du A oder B drückst.

### Platte und Touch Strip
- Berühren heißt Hand auf der Platte, Bewegen scratcht.
- **Loslassen:** Der Teller läuft weiter (Einstellung **WEITERLAUF**, Standard). Ein gestoppter Teller startet beim Loslassen, wie bei einem echten DJ-Deck. Mit **STOP** bleibt er stehen.
- **SLIP** (Pad 16): Während du scratchst, läuft die Platte im Hintergrund weiter. Beim Loslassen geht es genau dort weiter, wo der Track ohne Scratch wäre.
- **Sicherheit:** Meldet der Strip 1 s lang nichts mehr, gilt die Hand als weg. So bleibt die Platte nie hängen.

### Crossfader und Cut
- Links ist Deck A, rechts Deck B. Q-Link 1 ist der Crossfader.
- **CURVE** reicht von SMOOTH bis RAZOR. Das Kurvenbild zeigt, wie der Fader gerade arbeitet.
- **CUT ZU / CUT AUF** gilt für Pad 9:
  - CUT ZU: Halten macht das aktive Deck stumm.
  - CUT AUF: Das Deck klingt nur, solange du hältst. Das ist ideal für Forwards, Chirps und Transformer.

### SIMPLE / ADVANCED
Die Taste **ADVANCED** unten rechts schaltet den erweiterten Modus ein.
- Ein oranger Rahmen mit der Aufschrift ADVANCED zeigt, dass er an ist.
- Die Knöpfe werden zu SMOOTH, CATCH, CUT LAG und CRACKLE.
- Auf dem Plattenspieler erscheint ein ADVANCED-Feld mit HAMSTER, WEITERLAUF, CUE SETZEN, FIRE = PLAY, LOOP und DECK ON.

### Drei Ansichten (Layouts)
Tippe auf den **runden Knopf oben links** (die Zielleuchte des Plattenspielers). Jeder Tipp wechselt zur nächsten Ansicht. Du kannst die Ansicht auch in SETUP wählen.
1. **STUDIO:** ein großer Plattenspieler mit Mixer und Pads.
2. **BATTLE:** beide Plattenspieler nebeneinander, der Crossfader in der Mitte, die Pads unten. Das aktive Deck leuchtet orange.
3. **PADS:** große Pads zum Spielen, dazu Crossfader und Regler. Diese Ansicht braucht am wenigsten Rechenleistung.

## Turntable-Stile (pro Deck)
Jeder Stil ändert den Klang, das Aussehen und das Spielgefühl.

| Stil | Motor | Platte unter der Hand | Gleichlauf | Klang |
|---|---|---|---|---|
| **DD SILBER** | Direktantrieb, normal | normal | sehr stabil | voll, sauber |
| **BATTLE** | sehr starkes Drehmoment (Start/Stopp blitzschnell, fängt sofort) | leicht, direkt | quarzstabil | voll, sauber |
| **RIEMEN 70ER** | schwacher Riemen (langer Anlauf, rutscht, fängt spät) | schwer, träge | leichtes Leiern | warm, etwas Rumpeln und Staub |

## BROWSER
- **Links die Ordner, in der Mitte die Dateien.** Tippe einfach auf eine Zeile. Mit den Pfeilen blätterst du um eine Zeile, mit den Doppelpfeilen um eine Seite. Q-Link 1 wählt den Ordner, Q-Link 2 die Datei.
- **AUTO-HÖREN** (an): Tippen auf eine Datei spielt sie gleich an. **VORHÖREN** startet und stoppt das Anhören von Hand.
- **Laden:** Ziel-Deck wählen und auf einen der 8 Slots tippen. Die Datei liegt sofort auf der Platte.
- **Was durchsucht wird:** die eingebauten Samples, `My Samples` im Plugin-Ordner und alle Laufwerke bis 7 Ordner tief. Die Suche läuft im Hintergrund und bremst nichts. **NEU SUCHEN** liest die Laufwerke neu ein.
- **Grenzen:** Pro Slot werden höchstens 15 s geladen (WAV, mono oder stereo). Die Belegung wird im Projekt gespeichert.

## LERNEN – der Scratch-Lehrer
1. **Lektion wählen:**
   1. BABY SCRATCH
   2. DRAG
   3. FORWARD
   4. CHIRP
   5. TRANSFORMER
   6. TEAR
2. **DEMO:** Der Lehrer spielt die Lektion zwei Takte lang auf dem aktiven Deck vor (oben steht „HÖR ZU“). Danach bist du automatisch dran.
3. **ÜBEN:** Ein Takt wird vorgezählt („ZÄHL MIT … 1 2 3 4“), dann steht oben „JETZT DU!“.
4. **Die Spur** läuft von rechts nach links:
   - Die **grüne Linie** ist deine Hand: oben heißt vor, unten heißt zurück.
   - Die **orangen Balken** zeigen, wann Ton sein soll.
   - Der weiße Strich ist **jetzt**. Du siehst also schon, was als Nächstes kommt.
5. **Die Rückmeldung:**
   - LEHRER und DU zeigen den grünen Punkt (Soll) und deinen Finger (Ist) auf dem Strip.
   - **SCHRITT** wird nach jedem Schritt grün mit Haken oder rot mit X.
   - **TON SOLL** und **TON IST** zeigen, ob das Deck klingen soll und ob es klingt.
   - Nach jedem Takt gibt es einen Tipp, zum Beispiel „FALSCHE RICHTUNG“, „MEHR BEWEGUNG“, „ZU FRÜH“, „ZU SPÄT“ oder „TON AN/AUS …“.
   - Nach vier Takten gibt es 0–3 Sterne. Bei *** steigt das Tempo um 6 BPM.
6. **Vorbereitung durch den Lehrer:** Er stoppt den Motor, stellt CUT passend ein und öffnet den Crossfader zum aktiven Deck.

Die Anfänger-Presets (BABY SCRATCH, DRAG, FORWARD, CHIRP, TRANSFORMER, TEAR) wählen gleich die passende Lektion.

## Presets
INIT, BABY SCRATCH, DRAG, FORWARD, CHIRP, TRANSFORMER, TEAR, BATTLE TIGHT, 45 HYPE, DUSTY BELT.

## Bild im MPC-Browser
Im Plugin-Ordner unter `Plugin Skins/browser_images/` liegen zwei Bilder, nach Akais Muster für die eigenen Plugins:
- `trackedit.png`: das runde Bild, 64 px, die LP mit JF-Label.
- `soundsmode.png`: die Kachel im Sounds-Reiter, 270 × 110.

Ob die MPC diese Bilder auch bei externen VST-Plugins anzeigt, ist noch nicht bestätigt.

## Technik (ehrlich)
- **Hand:**
  - Eingaben kommen über Pitch Bend (14 Bit, sample-genau), Mod Wheel, Q-Link (SCRATCH), die Platte auf dem Bildschirm oder Pad HOLD.
  - Das Ziel gleitet über den gemessenen Meldeabstand. Danach glättet eine kritisch gedämpfte Feder die Bewegung, damit kein Zippern entsteht.
  - Am PC getestet: Die Tonhöhe folgt auf ±2 Cent. Aliasing bei 30-facher Geschwindigkeit liegt 30 dB unter dem Ton (6 Mipmap-Stufen).
- **Speicher:** bis 16 Samples à 15 s, als Mipmap etwa 2× so groß. Mit typischen kurzen Scratch-Samples sind das wenige MB.
- **Threads:** Es gibt drei getrennte Hintergrund-Threads.
  - Der **Melder** (alle 15 ms) gibt Tastendrücke, Texte und Live-Werte an die MPC weiter.
  - Der **Lader** lädt Samples und das Vorhören.
  - Der **Sucher** durchsucht die Laufwerke.
  - Lader und Sucher laufen mit niedriger Priorität. So bremst eine Laufwerkssuche weder Tasten noch Ton.
- **Eine Bediengruppe für das aktive Deck:** Die Regler auf dem Bildschirm schreiben in Stellvertreter-Parameter. Das Plugin spiegelt sie zu Deck A oder B, deshalb gibt es keine doppelten, übereinanderliegenden Regler.
- **Texte:** Die MPC zeigt höchstens 31 Zeichen pro Wert, deshalb sind die Tipps kurz.
- **Noch nicht auf der MPC getestet:** CPU-Last mit zwei Decks und Lehrer, flüssige Anzeige beim Deckwechsel, Laufwerkspfade der MPC für den Browser.

## Lizenzen
- Code: MIT.
- Samples: selbst synthetisiert.
- Grafiken: eigene Renderings mit dem JF-Logo des Erstellers.
- Schriften in den Bildern: Rajdhani und Titillium Web (SIL OFL).
