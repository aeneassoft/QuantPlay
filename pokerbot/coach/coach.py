"""Claude-backed poker coach, grounded in the knowledge extracted from the 3 books.

On-demand (not per action): explains the bot's move, reviews the player's move vs the GTO
baseline, and answers free-form questions. The extracted concepts + verified math are
injected into a cached system prompt so coaching cites real book principles.
"""
from __future__ import annotations

import json

import anthropic

from pokerbot import config


def _load_knowledge(max_concepts: int = 180, max_chars: int = 14000) -> str:
    parts: list[str] = []
    cpath = config.CONCEPTS_DIR / "concepts.json"
    if cpath.exists():
        try:
            concepts = json.loads(cpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            concepts = []
        parts.append("PRINCIPLES (from the books):")
        for c in concepts[:max_concepts]:
            tag = "EXPLOIT" if c.get("exploitative") else "GTO"
            line = f"- [{c.get('category','general')}/{tag}] {c.get('title','')}: {c.get('actionable_rule','')}"
            parts.append(line)
    mpath = config.MATH_DIR / "math.json"
    if mpath.exists():
        try:
            formulas = json.loads(mpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            formulas = []
        parts.append("\nMATH (verified):")
        for f in formulas:
            plain = " ".join(str(f.get("formula_plain", "")).split())[:160]
            parts.append(f"- {f.get('name','')}: {plain}")
    text = "\n".join(parts)
    return text[:max_chars] if text else "(knowledge base not yet available)"


def describe_hand(state: dict, hero_idx: int) -> str:
    bb = state["bb"]
    hero = state["players"][hero_idx]
    villain = state["players"][1 - hero_idx]
    hero_pos = "SB/BTN (in position postflop)" if hero["is_button"] else "BB (out of position postflop)"
    lines = [
        f"Street: {state['street']}",
        f"Your position: {hero_pos}",
        f"Your hand: {' '.join(hero['hole'])}",
        f"Board: {' '.join(state['board']) or '(none)'}",
        f"Pot: {state['pot']/bb:.1f}bb | Your stack: {hero['stack']/bb:.1f}bb | "
        f"Villain stack: {villain['stack']/bb:.1f}bb",
    ]
    if state.get("history"):
        acts = []
        for h in state["history"]:
            if h.get("action") == "deal":
                acts.append(f"[{h['street']}: {' '.join(h.get('board', []))}]")
            elif "action" in h:
                who = state["players"][h["player"]]["name"] if "player" in h else "?"
                amt = h.get("to") or h.get("amount")
                acts.append(f"{who} {h['action']}" + (f" {amt/bb:.1f}bb" if amt else ""))
        lines.append("Action: " + "; ".join(acts))
    return "\n".join(lines)


class Coach:
    def __init__(self, model: str | None = None, language: str = "de"):
        self.model = model or config.CLAUDE_MODEL
        self.language = language
        self._client = (anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
                        if config.ANTHROPIC_API_KEY else None)
        self._knowledge = _load_knowledge()

    @property
    def available(self) -> bool:
        return self._client is not None

    def _system(self) -> list[dict]:
        lang = {"de": "German", "en": "English"}.get(self.language, self.language)
        prompt = (
            f"You are a world-class Heads-Up No-Limit Hold'em coach. You teach using the "
            f"principles and math distilled below from three classic poker books (Modern Poker "
            f"Theory, The Theory of Poker, No-Limit Hold'em: Theory and Practice). "
            f"Be concise, concrete, and encouraging. Reference the relevant principle or piece of "
            f"math by name when it applies (pot odds, MDF, equity, range, position, etc.). "
            f"Always answer in {lang}. Keep answers to a few sentences unless asked for more.\n\n"
            f"{self._knowledge}"
        )
        return [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]

    def _chat(self, user: str, max_tokens: int = 700) -> str:
        if not self._client:
            return "(Coaching unavailable — no Claude API key found.)"
        try:
            msg = self._client.messages.create(
                model=self.model, max_tokens=max_tokens,
                system=self._system(),
                messages=[{"role": "user", "content": user}],
            )
            return "".join(b.text for b in msg.content if b.type == "text").strip()
        except Exception as e:  # noqa: BLE001
            return f"(Coach error: {type(e).__name__}: {e})"

    # --- public coaching surfaces ---------------------------------------
    def explain_move(self, state: dict, hero_idx: int, decision: dict) -> str:
        rationale = decision.get("rationale", {})
        user = (f"Explain the bot's decision to the player so they learn.\n\n"
                f"{describe_hand(state, hero_idx)}\n\n"
                f"Bot action: {decision['action']}"
                + (f" to {decision['amount']}" if decision.get('amount') else "") + "\n"
                f"Bot's internal reasoning: {json.dumps(rationale, ensure_ascii=False)}\n\n"
                f"In 2-4 sentences, explain WHY this is a good play and which principle it uses.")
        return self._chat(user)

    def review_user_move(self, state: dict, hero_idx: int, user_action: str,
                         user_amount, bot_decision: dict) -> str:
        user = (f"Review the player's decision like a coach. Be honest but constructive.\n\n"
                f"{describe_hand(state, hero_idx)}\n\n"
                f"Player chose: {user_action}" + (f" {user_amount}" if user_amount else "") + "\n"
                f"The GTO/bot baseline would: {bot_decision['action']}"
                + (f" to {bot_decision['amount']}" if bot_decision.get('amount') else "") + "\n"
                f"Baseline reasoning: {json.dumps(bot_decision.get('rationale', {}), ensure_ascii=False)}\n\n"
                f"If the player's move is fine, say so and explain why. If it's a mistake, explain the leak "
                f"and give one concrete tip. 2-5 sentences.")
        return self._chat(user)

    def ask(self, question: str, state: dict | None = None, hero_idx: int = 0) -> str:
        ctx = f"Current hand:\n{describe_hand(state, hero_idx)}\n\n" if state else ""
        return self._chat(ctx + "Player asks: " + question, max_tokens=900)
