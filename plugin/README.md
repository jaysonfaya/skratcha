# SKRATCHA 2.6.0 – zwei Scratch-Plattenspieler für die MPC

Von **JJ DA PLUG**. Instrument-Plugin für die MPC Live III / XL (arm64) und die MPC Live / Live II / One (arm32), gebaut mit dem offiziellen MPC Plugin SDK.

SKRATCHA hat zwei Decks mit je acht Sample-Slots und einen Battle-Crossfader. Gescratcht wird mit dem Touch Strip. Dazu gibt es drei Plattenspieler-Stile und einen Scratch-Lehrer.

## Installation
1. Die Ordner `JJ DA PLUG - VST - SKRATCHA` und `JJ DA PLUG - VST - SKRATCHA FEED` in den Ordner `VST2 Plugins` auf einem Laufwerk kopieren (USB, SD oder SSD). FEED brauchst du nur für LIVE / REC.
2. Voraussetzungen an der MPC:
   - MPC OS 3.10.1 oder neuer.
   - Preferences → Enhancements (Beta) → **Enable Enhancements** und **External Plugin Support** einschalten.
3. Einen Plugin-Track anlegen und SKRATCHA (JJ DA PLUG) wählen.
4. Den Touch Strip auf **PITCH BEND** stellen (SHIFT + Touch Strip).

**Zurück:** Die Ordner wieder löschen. Am System wird nichts verändert.

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
- **Gleich laut:** Seit 2.4 misst SKRATCHA laufend, wie laut deine Platte ohne Färbung wäre, und bringt jeden Plattenspieler genau auf diese Lautheit. Der Charakter bleibt, nur der Pegel springt beim Wechsel nicht mehr. Ein Schutz verhindert, dass der Ausgang über 0 dBFS geht.
- **Weicher Wechsel:** Beim Wechsel wird das Bild kurz abgedunkelt (etwa 30 ms), Plattenspieler und Label wechseln im dunkelsten Moment, dann hellt es wieder auf (etwa 100 ms). Es blitzt kein anderes Design mehr durch.

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
- **Blättern:** Finger auf die Liste legen und nach oben oder unten wischen. Wie schnell das geht, stellst du rechts unten bei **WISCH-TEMPO** ein (LANGSAM / NORMAL / SCHNELL). Der orange Schieber, die Pfeile und Q-Link 1 und 2 gehen weiterhin.
- **Ordner öffnen:** Auf den Pfeil **▶** am Ende der Zeile tippen oder doppelt auf den Namen tippen. **[..] ZURÜCK** oder ZURÜCK geht eine Ebene hoch. Rechts stehen die WAVs des geöffneten Ordners.
- **Sample laden:** Auf das **+** am Ende der Zeile tippen oder doppelt auf den Namen tippen. Das Sample liegt dann im aktuellen Slot (Pad) des aktiven Decks.
- **In einen bestimmten Slot:** Sample wählen, dann auf einen der 8 Slots rechts tippen.
- **Alle Sounds:** Seit 2.4.1 zeigt die Liste WAV, AIFF, MP3 und FLAC. Bei MP3 und FLAC wird nur der Anfang geladen, höchstens 15 s.
- **UNTERORDNER** (Standard an): Rechts stehen alle Sounds des geöffneten Ordners **und aller Ordner darunter** (bis 8 Ebenen, höchstens 4000 Sounds). Unten steht „SUCHE ...“, solange noch gesucht wird. Die Liste füllt sich dabei laufend. Öffnest du einen anderen Ordner, bricht die Suche sofort ab.

## LIVE – aufnehmen und live scratchen (neu in 2.4)
Dafür gibt es das zweite Plugin **SKRATCHA FEED**. Es kommt als Insert auf die Spur, die du scratchen willst: einen Drum-Track, einen Sample-Track, den Master oder eine Audio-Spur mit dem Eingang.

**Einrichten (einmal):**
1. Auf der Spur, die du scratchen willst: Insert-FX-Slot → **SKRATCHA FEED** (JJ DA PLUG).
2. Im FEED **Channel = FEED 1** lassen. Hast du mehrere Quellen, nimm FEED 2–4.
3. In SKRATCHA → Reiter **LIVE** → **QUELLE = FEED 1**. Oben steht dann „FEED 1: OK“.

**Aufnehmen (Resample):**
- **REC** tippen: Die Aufnahme startet. Nochmal **REC**: Sie stoppt (höchstens 15 s). Der rote Ring leuchtet, solange aufgenommen wird.
- **LETZTE 2 S / 4 S / 8 S:** Holt sofort die letzten Sekunden. Der FEED merkt sich immer die letzten etwa 11 s.
- Die Aufnahme landet im **aktuellen Slot des aktiven Decks** und liegt sofort auf dem Teller.
- Gespeichert wird sie als WAV in `My Samples/SKRATCHA REC` im Plugin-Ordner. So kennt das Projekt sie auch nach dem Neuladen. Ist das Laufwerk schreibgeschützt, bleibt sie nur im Speicher.

**Live scratchen:**
- **LIVE SCRATCH** tippen: Das aktive Deck spielt jetzt die Spur selbst, wie eine Platte. Der Touch Strip scratcht sie.
- Mit **Live Mode = REPLACE** im FEED (Standard) spielt die Spur während LIVE die gescratchte Version. Das passt zu einem DJ mit Platte. Der Crossfader und CUT gelten auch für die Spur.
- **NACH DEM LOSLASSEN:**
  - **SOFORT ZURÜCK** (Standard): Die Spur ist sofort wieder genau im Beat.
  - **BLEIBT HINTEN:** Die Platte läuft dort weiter, wo du sie losgelassen hast, wie bei einem echten Plattenspieler.
- LIVE nochmal tippen: Das Deck spielt wieder seinen Slot, die Spur läuft normal.
- **Latenz:** Während LIVE kommt die Spur etwa 14 ms später, bei 128er-Audioblöcken. Bei größeren Blöcken der MPC ist es entsprechend mehr.
- **Master:** FEED geht auch auf den Master. SKRATCHA schickt das live gescratchte Deck dann nur über den FEED zurück, nicht zusätzlich über die eigene Spur. So entsteht keine Rückkopplung.

## SC6000M / MIDI-Controller (neu in 2.5)
- **Reiter SC6000M:** Test-Assistent mit 12 Schritten und ein MIDI-Monitor, der zeigt, was gerade ankommt. Alles wird in einem Protokoll gespeichert: `SKRATCHA MIDI LOG/MIDI <Datum>.txt` im Plugin-Ordner.
- **Teller erkennen:** Bei Schritt 2 (Motor läuft 10 s auf 33 U/min) findet SKRATCHA die Teller-Meldung selbst. Erkannt werden relative CCs (64 ± oder Zweierkomplement), absolute 7- und 14-Bit-CCs und Pitch Bend. SKRATCHA misst auch, wie viele Schritte eine Umdrehung hat. Ohne Motor geht es über Schritt 7 (genau 1 Umdrehung von Hand).
- **TELLER FOLGT:** Das aktive Deck folgt dem echten Teller. 1 Umdrehung bei 33 1/3 (oder 45) entspricht der normalen Geschwindigkeit, egal welcher Plattenspieler im Plugin gewählt ist. Steht der Teller still, steht die Platte. Der zweite Layer (nächster MIDI-Kanal) schaltet auf Deck B.
- Solange der Test läuft, steuern MIDI-Daten nichts in SKRATCHA. Bei TELLER FOLGT lösen alle Meldungen, die der Controller beim Test geschickt hat, keine Pads aus.
- **Neu in 2.6: Controller = SC6000M** (unten links im Reiter SC6000M). Das feste Profil stammt aus deinem Protokoll vom 18.11.:
  - **Teller:** Bewegung über CC55/CC54 (14 Bit mit Vorzeichen, etwa 1000 Meldungen pro Sekunde). 3600 Schritte pro Umdrehung laut Denon. Beim Motorlauf vorwärts zählt der Teller rückwärts. Das ist eingerechnet, mit TELLER-RICHTUNG lässt es sich umdrehen. Mit diesem Profil folgt das Deck dem Teller immer.
  - **Pitch-Fader:** CC8/CC40 → Pitch des Decks (oben = minus, wie bei Denon). Er wirkt auch auf den mitlaufenden Teller.
  - **Tasten:** PLAY (Note 1) = Start/Stop, CUE (Note 2) = zurück an den Anfang der Platte, Pads 1–8 (Noten 32–39) = die 8 Platten des Decks.
  - **Layer:** Layer A = Kanal 1 = Deck A, Layer B = Kanal 2 = Deck B.
  - Den Pitch-Bend-Strom des SC6000M schluckt SKRATCHA nur, solange der Teller läuft. Der Touch Strip der MPC funktioniert also weiter.
  - Alle anderen SC6000M-Tasten tun noch nichts.
- **Neu in 2.7: Platter Mode HAND / MOTOR** (Reiter SC6000M, neben TELLER FOLGT). Im Computer-Modus dreht der Motor des SC6000M nicht – der Teller ist dann wie ein grosses Jogwheel.
  - **HAND (Standard):** Der SKRATCHA-Motor spielt die Platte. PLAY am SC6000M startet und stoppt. Sobald du den Teller drehst, ist das deine Hand auf der Platte (Scratch, Backspin, Abbremsen). Lässt du los, läuft die Platte mit dem Plugin-Motor weiter (wie „After Scratch = RUN ON“). Der Pitch-Fader des SC6000M stellt das Pitch des Decks.
  - **MOTOR:** Nur wenn der Teller wirklich vom Motor gedreht wird. Dann ist der Teller die Platte selbst; steht er, steht die Platte.
- **Neu in 2.7.1: MOTOR SUCHEN** (Reiter SC6000M, links unten). Sucht automatisch den Befehl, mit dem der SC6000M-Motor im Computer-Modus anläuft: SKRATCHA schickt nacheinander alle Noten und CCs über die MIDI-Verbindung der MPC an den SC6000M und misst, ob der Teller danach dreht. Dauer ca. 9 Minuten, Fortschritt in der gelben Teller-Zeile. Protokoll: `/tmp/sc-motor.log` und `SKRATCHA MIDI LOG/MOTOR-SUCHE.txt`. Abbrechen: Schalter wieder aus.
- **Neu in 2.8: Echter SC6000M-Motor.** Controller = SC6000M und Platter Mode = MOTOR: PLAY am SC6000M (oder PLAY im Plugin) startet den echten Teller-Motor, nochmal PLAY hält ihn an. Der drehende Teller ist die Platte – anfassen, bremsen, scratchen wie auf einem Plattenspieler. Gefunden mit MOTOR SUCHEN / STOP SUCHEN: Start = CC 65 (127), Stop = CC 66 (127, dann 0). SKRATCHA sendet über einen eigenen ALSA-Sequencer-Anschluss direkt an den SC6000M; beim Schliessen des Plugins wird der Motor gestoppt. Layer B = MIDI-Kanal 2 (noch ungetestet).
- **Grenzen:** Lichter und Display des SC6000M steuert SKRATCHA nicht. Motor, Lichter und Display des SC6000M lassen sich deshalb nicht vom Plugin steuern. Ob die MPC den SC6000M als MIDI-Gerät annimmt, zeigt erst der Test.

## LERNEN
- **0 GRUNDLAGEN:** Tippe ÜBEN. In 10 Schritten lernst du START, STOP, Sample wählen, Strip berühren, scratchen, loslassen, CUT, Crossfader, Deck B und zurück zu Deck A.
  - Jeder Schritt geht erst weiter, wenn du ihn wirklich gemacht hast.
  - Rechts zeigt ein **MPC-Bild**, welches Pad, welcher Strip oder welcher Q-Link gerade dran ist.
- **1–6 Scratch-Lektionen:** wie in 2.1, mit genauerer Auswertung.
  - Die Richtung deiner Hand wird über den ganzen Schritt geprüft, nicht nur am Anfang und am Ende.
  - Die **SYNC-Anzeige** (10 LEDs) zeigt live, wie gut du der grünen Linie folgst.
  - Auch hier zeigt das MPC-Bild, was du benutzen sollst, zum Beispiel Strip und Pad 9 für Forward und Chirp.

## Mitgelieferte Samples
- **Deck A – alte Radioreden (gemeinfrei):**
  - 01–06 **FDR 1941:** Franklin D. Roosevelts Rede vor dem Kongress am 8. Dezember 1941.
  - 07–08 **ARMSTRONG 1969:** Neil Armstrong bei der Mondlandung.
  - Die Reden sind in kurze Phrasen geschnitten, gefiltert und normalisiert. Quellen und Lizenzen stehen in `Content/CREDITS.txt`.
- **Deck B – eigene Sounds (21–34):** AHH, FRESH, YEAH, HEY, UH, GO, COME ON, CHECK IT, BREAK 92, STAB, HORN, BASS DROP, OOH WAH, TONE 1K. Alle sind selbst synthetisiert.
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
- **Neu in 2.5:** DC-Blocker (3 Hz) am Ausgang. Eine still gehaltene Platte hinterlässt so keinen Gleichspannungs-Versatz mehr.
- **Neu in 2.4:**
  - Lautheit pro Deck: gewichtete Leistung vor und nach der Era-Färbung (250 ms). Daraus wird eine Ausgleichs-Verstärkung (0,3–2,8×, 40 ms Gleiten), danach ein Sicherheits-Begrenzer ab −1 dBFS. Am PC gemessen liegen die 10 Plattenspieler mit Sprache innerhalb 0,5 dB, mit Break und Vocal innerhalb etwa 1,4 dB.
  - Designwechsel: alle Decks in einem Filmstreifen, die Labels sind immer da (Bild 0 leer). Nichts wird mehr ein- oder ausgeblendet.
  - Browser: Die Zeilen sind gleich gebaut wie der Schieber, der auf der MPC funktioniert. Wischen schiebt die Liste; Doppeltipp und der Zeilen-Pfeil öffnen bzw. laden.
  - LIVE: Ein Ring im geteilten Speicher, aus dem SKRATCHA laufend die Mip-Stufen baut. Am PC mit beiden Plugins getestet: Pegel gleich, keine Knackser, Scratch und Zurückspringen funktionieren, die Latenz liegt bei 13,9 ms, REC und GRAB liefern WAVs der richtigen Länge.
- **Neu in 2.3 – Timing:**
  - **Loslassen = AUTO** (neuer Standard). Die Platte läuft weiter, sobald der Strip in die Mitte springt **oder** dein Finger 55 ms lang keine Bewegung mehr meldet. Vorher wartete das Plugin bis zu 1 s, weil der MPC-Strip beim Loslassen nicht immer die Mitte sendet.
  - Am PC gemessen: Vom Loslassen bis zum vollen Tempo dauert es jetzt etwa 55 ms, ohne Mitte-Signal etwa 100 ms. In 2.2 war es bis zu 1 s.
  - **Start 300 ms, Bremse 400 ms** (vorher 700 / 900). Das entspricht einem schnellen Battle-Plattenspieler. In SETUP lässt sich beides wie bisher ändern.
  - **Catch 15 ms, Smooth 1,6 ms, Gleiten höchstens 6 ms.** Die Platte hängt damit enger an deiner Hand. Die Tonhöhe folgt weiterhin auf wenige Cent genau.
  - **Wichtig:** Ein Finger, der still auf dem Strip liegt, gilt bei AUTO als losgelassen, denn der Strip meldet dann nichts. Zum Festhalten der Platte nimmst du das Pad **HOLD**.
  - Wer das alte Verhalten will, stellt in SETUP **Loslassen** auf CENTER oder TIMEOUT.
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
- Decoder: dr_wav, dr_mp3, dr_flac von David Reid (`src/third_party/`, Public Domain / MIT No Attribution).
- Samples: Reden FDR 1941 (Public Domain Mark 1.0) und Armstrong 1969 (NASA, gemeinfrei), von Wikimedia Commons. Die übrigen Sounds sind selbst synthetisiert.
- Grafiken: eigene Renderings mit dem JF-Logo des Erstellers.
- Schriften in den Bildern: Rajdhani und Titillium Web (SIL OFL).
