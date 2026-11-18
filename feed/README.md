# SKRATCHA FEED – by JJ DA PLUG

Insert-Effekt, der eine Spur (oder den Master oder den Eingang) an SKRATCHA weitergibt.

- **Channel (FEED 1–4):** muss mit **QUELLE** im Reiter LIVE von SKRATCHA übereinstimmen.
- **Live Mode:**
  - **REPLACE** (Standard): Solange SKRATCHA diese Spur LIVE scratcht, spielt die Spur die gescratchte Version. Sonst läuft sie unverändert durch.
  - **ALWAYS DRY:** Die Spur bleibt immer unverändert. SKRATCHA spielt das Scratchen dann auf seiner eigenen Spur.
- **Feed Level:** Pegel, mit dem die Spur bei SKRATCHA ankommt.
- **Status:** zeigt, ob SKRATCHA gerade live ist.

Technik: Die Verbindung liegt im flüchtigen Arbeitsspeicher (Shared Memory, tmpfs). Sie verschwindet, wenn der letzte FEED entfernt wird oder die MPC neu startet. FEED schreibt nichts auf ein Laufwerk und ändert nichts am System.
Latenz im LIVE-Modus: 2 Audioblöcke + 128 Samples beim FEED und 1 Block + 96 Samples bei SKRATCHA, bei 128er-Blöcken etwa 14 ms.
CPU: sehr gering (kopieren, kein DSP).
