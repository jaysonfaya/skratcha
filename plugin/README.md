# SKRATCHA 2.2 – zwei Scratch-Plattenspieler für die MPC

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
| | Spalte 1 | Spalte 2 | Spalte 3 | Spalte 4 |
|---|---|---|---|---|
| **oben (13–16)** | DECK A | DECK B | REVERSE | SLIP |
| **(9–12)** | CUT | HOLD | CUE | START / STOP |
| **(5–8)** | Sample 5 | Sample 6 | Sample 7 | Sample 8 |
| **unten (1–4)** | Sample 1 | Sample 2 | Sample 3 | Sample 4 |

- Alles geht auch per Touch: Tippen auf dem Bildschirm macht dasselbe wie das Pad.
  - CUT und HOLD rasten per Touch ein: einmal tippen ist an, nochmal tippen ist aus.
  - Auf der Hardware wirken CUT und HOLD, solange du das Pad hältst.
- **HOLD + CUE** setzt den Cue-Punkt.
- **BATTLE-Ansicht:** Die Pads sind geteilt und gespiegelt. Links liegt Deck A, rechts Deck B.

  | | A außen | A innen | B innen | B außen |
  |---|---|---|---|---|
  | **oben** | START A | DECK A | DECK B | START B |
  | | CUT A | CUE A | CUE B | CUT B |
  | | Sample 3 | Sample 4 | Sample 4 | Sample 3 |
  | **unten** | Sample 1 | Sample 2 | Sample 2 | Sample 1 |

### Platte
- **Das Sample läuft immer im Loop** (wie eine Endlosrille). Es ist also immer Ton da.
- Berührst du den Strip, liegt deine Hand auf der Platte; Bewegen scratcht.
- Beim Loslassen läuft der Teller weiter (WEITERLAUF).
- **SLIP** (Pad 16): Während du scratchst, läuft die Platte im Hintergrund weiter.

### Zwei Tasten für Look und Ansicht
- **Die runde Leuchte oben links** (versteckte Taste): Jeder Tipp macht aus dem aktiven Deck den nächsten der 10 Plattenspieler. Aussehen, Platte, Label, Klang und Spielgefühl ändern sich mit. Im LCD steht, welcher es ist.
- **ANSICHT WECHSELN** (sichtbare Taste): In der Taste steht, was du jetzt hast und was ein Tipp bringt. Zum Beispiel „JETZT STUDIO > BATTLE“.
  - STUDIO: ein großer Plattenspieler.
  - BATTLE: zwei Decks nebeneinander.
  - PADS: große Pads.

### Crossfader, CUT, ADVANCED
- **Crossfader:** Q-Link 1. Die CURVE reicht von SMOOTH bis RAZOR, das Kurvenbild zeigt sie. Dazu kommen CUT LAG und HAMSTER.
- **CUT ZU / CUT AUF:**
  - CUT ZU: Pad 9 macht das Deck stumm.
  - CUT AUF: Das Deck klingt nur, solange Pad 9 gehalten wird.
- **ADVANCED:** Ein oranger Rahmen um die Profi-Knöpfe (SMOOTH, CATCH, CUT LAG, CRACKLE) zeigt, dass es an ist. Dazu kommt ein Feld neben der ANSICHT-Taste mit HAMSTER, WEITERLAUF, CUE SETZEN, FIRE=PLAY, DECK ON und SLIP.

## Die 10 Plattenspieler
Jeder Plattenspieler hat eine eigene Platte und ein eigenes Label, immer mit dem JF-Logo in passender Farbe. Dazu einen eigenen Klang und ein eigenes Gefühl.

| Plattenspieler | Look / Platte | Klang | Gefühl |
|---|---|---|---|
| 1912 GRAMMOPHON | Eiche, Messing, Schellack, cremefarbenes Label | 78 rpm, Trichter-Mitten (Bandpass mit Resonanz), mono, Rauschen, viel Staub | Federwerk: träge, starkes Leiern |
| 1935 SCHELLACK | Bakelit, blaues Label, silbernes Logo | 78 rpm, mono, schmal, Rauschen | schwer, langsam |
| 1955 RÖHRENTRUHE | Mahagoni, rotes Label | Röhren-Sättigung, warm, mono, Rumpeln | schwer, langsam |
| 1965 KOFFER | Türkis-Leder, rote Vinylplatte | kleiner Lautsprecher (Mitten-Box), mono | leichter Teller, schwacher Motor, Leiern |
| 1974 RIEMEN | Walnuss, oranges Label | warm, Rumpeln, etwas Staub | Riemen rutscht, fängt spät |
| 1978 DIRECT DRIVE | Silber, rotes Label mit Gold | sauber, voll | normal, stabil |
| 1986 BATTLE | Schwarz, Splatter-Vinyl, White Label | sauber, druckvoll | sehr starkes Drehmoment |
| 1996 SCRATCH PRO | Gunmetal mit Gold, lila Marmor-Vinyl | Scratch-Tonabnehmer (Präsenz) | noch schneller, leicht |
| 2006 DVS TIMECODE | Weiß, blaue Timecode-Platte | absolut sauber | sofort, ohne Leiern |
| 2026 NEON FUTURE | Schwarzglas, Neon-Ring, Verlaufslabel | Bass-Punch, clean | blitzschnell |

## SETUP = die 16 Q-Links
Die vier Reihen auf dem Bildschirm sind genau die Q-Links: oben 13–16, unten 1–4.

| Reihe | Q-Links | Regler |
|---|---|---|
| 1 | 13–16 | Plattenspieler, Fire, Weiterlauf, Ansicht |
| 2 | 9–12 | Strip Range, Smooth, Catch, Loslassen |
| 3 | 5–8 | Fader Curve, Cut Lag, Cut Speed, Cut Mode |
| 4 | 1–4 | Start, Bremse, Pitch Range, Crackle |

Rechts liegen die Schalter per Touch: Slip, Hamster, Strip Invert, Pad 1 = C#1, Deck On, Reverse, Lehrer-Klick, Auto-Hören.

## BROWSER – alle Laufwerke der MPC
- **Die erste Ebene:** alle Laufwerke, das sind SKRATCHA SAMPLES, My Samples, jedes Laufwerk unter /media, /mnt usw., die interne SSD, die SD-Karte und MPC Content. Dazu **SYSTEM – ALLES (/)**, das ganze Dateisystem.
- **Ordner:** Tippen wählt den Ordner aus, rechts erscheinen seine WAVs. **Zweimal tippen** (oder ÖFFNEN) geht hinein, **[..] ZURÜCK** oder ZURÜCK geht eine Ebene hoch. Oben steht der Pfad.
- **Datei:** Tippen spielt sie mit AUTO-HÖREN an. **Zweimal tippen** (oder LADEN) legt sie in den aktuellen Slot des aktiven Decks.
- **Laden in einen bestimmten Slot:** Auf einen der 8 Slots rechts tippen.
- **Blättern:** Mit dem **orangen Schieber** neben jeder Liste wischst du durch die Liste. Die Pfeile springen eine Zeile oder eine Seite weiter. Q-Link 1 und 2 wählen Ordner und Datei.

## LERNEN
- **0 GRUNDLAGEN:** Tippe ÜBEN. In 10 Schritten lernst du START, STOP, Sample wählen, Strip berühren, scratchen, loslassen, CUT, Crossfader, Deck B und zurück zu Deck A.
  - Jeder Schritt geht erst weiter, wenn du ihn wirklich gemacht hast.
  - Rechts zeigt ein **MPC-Bild**, welches Pad, welcher Strip oder welcher Q-Link gerade dran ist.
- **1–6 Scratch-Lektionen:** wie in 2.1, mit genauerer Auswertung.
  - Die Richtung deiner Hand wird über den ganzen Schritt geprüft, nicht nur am Anfang und am Ende.
  - Die **SYNC-Anzeige** (10 LEDs) zeigt live, wie gut du der grünen Linie folgst.
  - Auch hier zeigt das MPC-Bild, was du benutzen sollst, zum Beispiel Strip und Pad 9 für Forward und Chirp.

## Mitgelieferte Samples
- **Vocals zum Scratchen:** AHH, FRESH, YEAH, HEY, UH, GO, COME ON, CHECK IT. Sie liegen auf Deck A.
- **Weitere Sounds:** BREAK 92, STAB, HORN, BASS DROP, OOH WAH, TONE 1K. Sie liegen auf Deck B.
- Alle sind selbst synthetisiert und damit frei.
- **Echte Acapellas** sind nicht dabei. Bei den freien Packs darf man die Dateien meistens nicht in einem Plugin weitergeben. Lade sie selbst herunter und finde sie dann über den BROWSER auf deinem Laufwerk. Quellen:
  - freesound.org: Filter „Creative Commons 0“, Suche „acapella“ oder „rap vocal“.
  - samplefocus.com: Einträge „Public Domain“.
  - Looperman-Acapellas: Die Lizenz der jeweiligen Uploader beachten.

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
