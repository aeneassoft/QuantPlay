"""HybridHero — das ECHTE 6-max-Produkt als EIN Agent: tag-Kern multiway, Prince sobald der Pot heads-up ist.

Gehoben aus research/sixmax_export.py (2026-09-09, reiner Move + `stack`): der Export-Kanal (Analyzer),
der Trainer-GTO-Modus (six_server.Session._prince_seat/_prince_decide) und das gepaarte 6-max-Gate
(pokerbot/autogym/pargate6.py) spielen damit denselben Verbund. Fail-soft wie bisher: jedes Prince-Problem
faellt still auf den Kern zurueck (Zaehler `kern_fallbacks` macht das sichtbar).
"""
from __future__ import annotations

from pokerbot.arena.sixmax import PROFILES, SixMaxBot

KERN_PROFIL = "tag"     # der Multiway-Kern des Produkts (sixmax_export --hero-profile Default)


class HybridHero:
    """tag-Kern multiway; sobald der Pot heads-up Hero-vs-EIN-Villain ist, entscheidet Prince ueber die
    HU-Projektion des Graders (oracle.record_to_hu_state). `stack` = Name der AUSLESE-Guard-Kette um den
    Prince-Anteil (None = nackter Prince v2.2 wie bisher; auslese.FINAL_STACK = die HU-App-Politik);
    `prince` = ein geteiltes PrinceOracle (pargate6 haelt EINE PokerBot-Instanz je Arm ueber alle Rotationen)."""

    def __init__(self, seat: int = 0, stack: str | None = None, seed: int | None = None,
                 prince=None, kanal: str = "gym"):
        from pokerbot.coach.oracle import PrinceOracle
        self.seat = seat
        self.bot = SixMaxBot(seat, PROFILES[KERN_PROFIL], seed=seed)
        self.bot._read = lambda obs: {}          # GTO-Modus-Paritaet: Liga-Exploit-Reads AUS
        self.prince = prince if prince is not None else PrinceOracle(stack=stack, kanal=kanal)
        self.table = None
        self.hand_id: str | None = None          # Adresse fuer Plan-Cache/private Randomisierung (K2); None = Export-Id
        self.prince_decisions = 0
        self.kern_fallbacks = 0

    # ---- Sitz-/Tisch-Protokoll (SixMaxBot-kompatibel, damit eine Arena beide gleich behandelt)
    def setze_sitz(self, seat: int) -> None:
        self.seat = seat
        self.bot.seat = seat

    def bind_table(self, table) -> None:
        self.table = table

    def new_hand(self, seats) -> None:
        self.bot.new_hand(seats)

    def observe(self, *args) -> None:
        self.bot.observe(*args)

    def _heads_up(self) -> bool:
        live = [i for i, s in enumerate(self.table.seats) if not s.folded]
        return len(live) == 2 and self.seat in live

    def _record(self) -> dict:
        from dataclasses import asdict

        from pokerbot.brain.format_spot import spot_from_table
        from pokerbot.coach.decision_log import spot_fingerprint
        t = self.table
        spot = asdict(spot_from_table(t, self.seat))
        return {"spot": spot, "obs": t.obs_for(self.seat), "legal": t.legal_actions(),
                "history": [dict(h) for h in t.history if "player" in h],
                "street": t.street, "hand_id": self.hand_id or f"exp-{t.hand_no}",
                "spot_fp": spot_fingerprint(spot)}

    def decide(self, obs):
        if self.table is not None and not self.table.hand_over and self._heads_up():
            try:
                dec = self.prince.decide(self._record())
                self.prince_decisions += 1
                return dec
            except Exception:  # noqa: BLE001 — fail-soft: der Kern spielt weiter
                self.kern_fallbacks += 1
        return self.bot.decide(obs)
