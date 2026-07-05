"""The interpretive layer of the deep report (plan 2026-07-01) — the ONLY paid step (OpenAI, PC-hub).

Numbers stay DETERMINISTIC + grounded here (the Poker-IQ dimensions are computed from real proxies); OpenAI writes only
the German PROSE that frames them. Hard rules pushed into the system prompt: no money, no 'losses'/'downswing', minimal
jargon (explained), preflop+postflop as ONE flowing field, warm/positive/engaging. Reuses research/llm.openai_json.
"""
from __future__ import annotations

import json
import os

from research import llm

STATS = "data/coach/deep_stats.json"
SIM = "data/coach/style_sim.json"
COACH = "data/coach/window_report.md"
OUT = "data/coach/synth.json"

# coaching classification of the 154-decision mid/high sample (from window_report.md header)
COACH_CLS = {"profitable_exploit": 60, "true_leak": 57, "gto_optimal": 31, "read_dependent": 6}

RULES = (
    "Du bist ein warmherziger, begeisterter Poker-Coach, der einen langen, motivierenden Spieler-Bericht auf DEUTSCH "
    "schreibt. HARTE REGELN, die du NIEMALS brichst: (1) Sprich NIE über Geld, Dollar oder Beträge — nur über "
    "'Low-/Mid-/High-Stakes'. (2) Sprich NIE über 'Verluste', 'Downswings' oder 'Miese' — formuliere Varianz IMMER "
    "als 'Schwankungsbreite', 'Ausschläge', 'Wucht'. (3) Minimaler Fachjargon — wenn ein Fachbegriff nötig ist, "
    "erkläre ihn sofort in Klammern in einfachen Worten. (4) Betrachte Pre-Flop und Post-Flop als EIN fließendes "
    "Feld — kein hartes Trennen. (5) Durchweg positiv, wertschätzend, konkret und mitreißend. Der Spieler ist ein "
    "starker, aggressiver Gewinner-Spieler; 'Schwächen' heißen 'Wachstumsfelder'."
)


def _pct(a, b):
    return round(100 * a / b, 1) if b else 0.0


def compute_iq(stats: dict, cls: dict) -> tuple[dict, int]:
    """Poker-IQ = a CONSTRUCTED index (labelled honestly). Each dimension 0–100 from a real proxy; headline on an
    IQ-like 100-centered scale. NOT canonical truth — a map of the player's shape."""
    ent = stats["entropy"]
    total_cls = sum(cls.values()) or 1
    good = cls["gto_optimal"] + cls["profitable_exploit"]          # solver-fine OR a profitable read
    overbet = ent["distribution"][">1.1x (overbet)"]
    over_share = _pct(overbet, ent["n_bets"])
    # loose = wide range; the discipline dimension is the (framed-positive) growth field
    n_classes = len({hc for pos in stats["ranges"].values() for role in pos.values() for hc in role})
    range_width = _pct(n_classes, 169)
    dims = {
        "Aggression":       min(96, round(55 + over_share * 0.9)),        # over-betting signature
        "Unberechenbarkeit": round(100 * ent["entropy_bits"] / ent["max_bits"]),  # sizing entropy
        "Anpassung":        min(92, round(50 + _pct(cls["profitable_exploit"], total_cls) * 0.9)),  # exploit share
        "Spiel-Qualität":   min(92, round(35 + _pct(good, total_cls))),   # solver-fine + profitable
        "Disziplin":        max(40, round(100 - range_width * 0.7)),      # tighter = higher (growth field)
        "Value-Ernte":      min(94, round(58 + over_share * 0.7)),        # gets paid via pressure + big sizing
    }
    composite = sum(dims.values()) / len(dims)
    headline = round(100 + (composite - 55) * 1.1)                        # ~115–133 for a strong aggressive winner
    return dims, headline


def _coach_lessons(n: int = 8) -> list[str]:
    if not os.path.exists(COACH):
        return []
    out = []
    for ln in open(COACH, encoding="utf-8"):
        if "**Lektion:**" in ln:
            out.append(ln.split("**Lektion:**", 1)[1].strip())
        if len(out) >= n:
            break
    return out


def _summary_for_llm(stats: dict, sim: dict | None, dims: dict, iq: int) -> dict:
    cls = COACH_CLS
    total = sum(cls.values())
    sim_findings = None
    if sim:
        per = {k: v["bb_per_100"] for k, v in sim["style_per_opponent"].items()}
        avg = round(sum(per.values()) / len(per))
        top = sorted(per, key=per.get, reverse=True)[:3]
        de = {"maniac": "Maniacs (wild)", "station": "Calling-Stations", "whale": "Whales (sehr locker)",
              "lag": "Loose-Aggressive", "tag": "Tight-Aggressive", "shark": "starke Regs", "nit": "Nits",
              "rock": "Rocks"}
        # ROBUST framing only — single-type tables are high-variance, so we hand the model the stable signal,
        # not the noisy per-matchup magnitudes (which flip between runs).
        sim_findings = {
            "stil_ist_durchweg_im_plus": avg > 0,
            "groesster_vorteil_gegen": [de.get(t, t) for t in top],
            "robust_ueber_beide_laeufe_dominiert": ["Maniacs (wild)", "Calling-Stations", "Whales"],
            "hohe_schwankungsbreite": True,
            "hinweis": ("Der Vorteil ist am größten gegen wilde/lockere Freizeit-Gegner (den Online-Pool); "
                        "gegen sehr disziplinierte Spezialisten wird es eng und die Schwankung groß."),
        }
    return {
        "hands_total": stats["n_hands"], "sessions": stats["n_sessions"], "by_tier": stats["by_tier"],
        "game_level_sessions": stats["game_level_dist"], "hands_by_level_pct":
            {k: _pct(v, stats["n_hands"]) for k, v in stats["hands_by_level"].items()},
        "session_examples": [{"date": s["date"], "tier": s["tier"], "level": s["game_level"],
                              "vpip": s["vpip"], "allin_rate": s["allin_rate"]} for s in stats["sessions"][:12]],
        "range_width_hands_played_of_169": len({hc for pos in stats["ranges"].values()
                                                for role in pos.values() for hc in role}),
        "sizing_entropy_bits_of_2": stats["entropy"]["entropy_bits"],
        "sizing_distribution": stats["entropy"]["distribution"],
        "variance_serious": stats["variance_serious"],
        "coaching_sample_classification": cls,
        "coaching_pct": {k: _pct(v, total) for k, v in cls.items()},
        "coaching_lessons_sample": _coach_lessons(),
        "poker_iq_dimensions": dims, "poker_iq_headline": iq,
        "bot_sim_findings": sim_findings,
    }


_PORTRAIT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["archetyp_name", "portrait", "glossar", "phasen", "strategie_fliessendes_feld",
                 "ranges_text", "confusion_text"],
    "properties": {
        "archetyp_name": {"type": "string", "description": "Ein griffiger Spitzname für den Spielstil, z.B. 'Der Sturm'"},
        "portrait": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3,
                     "description": "2–3 Absätze Spieler-Porträt"},
        "glossar": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                    "required": ["begriff", "erklaerung"],
                    "properties": {"begriff": {"type": "string"}, "erklaerung": {"type": "string"}}},
                    "minItems": 5, "maxItems": 8},
        "phasen": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4,
                   "description": "Absätze zu A/B/C-Game, wann playful, wie oft"},
        "strategie_fliessendes_feld": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
        "ranges_text": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
        "confusion_text": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
    },
}

_EDGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["wann_gefaehrlich", "varianz_text", "iq_text", "sim_lektionen", "andere_spieler", "fazit"],
    "properties": {
        "wann_gefaehrlich": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                             "required": ["situation", "warum"],
                             "properties": {"situation": {"type": "string"}, "warum": {"type": "string"}}},
                             "minItems": 3, "maxItems": 5},
        "varianz_text": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
        "iq_text": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
        "sim_lektionen": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
        "andere_spieler": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                           "required": ["name", "warum"],
                           "properties": {"name": {"type": "string"}, "warum": {"type": "string"}}},
                           "minItems": 2, "maxItems": 4},
        "fazit": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 3},
    },
}


def main():
    stats = json.load(open(STATS, encoding="utf-8"))
    sim = json.load(open(SIM, encoding="utf-8")) if os.path.exists(SIM) else None
    dims, iq = compute_iq(stats, COACH_CLS)
    summary = _summary_for_llm(stats, sim, dims, iq)
    payload = json.dumps(summary, ensure_ascii=False, indent=1)

    p_user = ("Hier sind die MESSDATEN eines Spielers (aus seiner echten Hand-History, 6 Monate). Schreibe die "
              "genannten Bericht-Abschnitte — lang, mitreißend, konkret an den Zahlen. Deute Pre- und Post-Flop als "
              "ein fließendes Feld. Daten:\n\n" + payload)
    portrait, u1 = llm.openai_json(RULES, p_user, _PORTRAIT_SCHEMA, "portrait", max_tokens=6000)

    e_user = ("Dieselben Messdaten. Schreibe jetzt die WEITEREN Abschnitte: wann der Spieler am gefährlichsten ist "
              "(3–5 konkrete Situationen), die Varianz als Schwankungsbreite, die Deutung des Spiel-IQ-Index, die "
              "Lektionen aus der Bot-Simulation seines Stils, welche bekannten Spielertypen/Pros ihm ähneln, und ein "
              "warmes Fazit mit seinen Kern-Stärken. Daten:\n\n" + payload)
    edge, u2 = llm.openai_json(RULES, e_user, _EDGE_SCHEMA, "edge", max_tokens=6000)

    result = {"dims": dims, "iq": iq, "portrait": portrait, "edge": edge,
              "tokens": {"portrait": u1, "edge": u2}}
    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tot_in = u1[0] + u2[0]
    tot_out = u1[1] + u2[1]
    print(f"IQ headline {iq} | dims {dims}")
    print(f"archetyp: {portrait['archetyp_name']}")
    print(f"tokens: {tot_in} in / {tot_out} out")
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
