## 1. WHERE the corset goes

Single chokepoint, **after** the LLM decides, **before** the action is returned:

`tools/gtow_client/src/poker_agent.py::GLMBrainAgent._decide`

```python
decision = brain.decide_spot(spot)          # {'action','amount'} from GLM
decision = river_corset(spot, decision, api) # <-- NEW, river-only no-op elsewhere
return decision
```

Put `river_corset` in `pokerbot/brain/api.py` (it only uses `api.*` + `spot`). This also covers `executor.py::run_program` since that path funnels back through `decide_spot`. Do **not** touch `bot.py` jam bounds — the corset is a post-decision clamp.

Key engine fact baked in: **use `api.required_equity(spot.to_call, spot.pot)`** (returns `B/(P+2B)` = `0.418` for 51-into-20). Never recompute `B/(P+3B)`.

## 2. Guard pseudocode (exact, `api.*`)

```python
VALUE_CLASSES = {'two_pair','set','straight','flush','full_house','quads','straight_flush'}
MARGIN = 0.03            # avoids over-folding marginal +EV / breakeven hands

def river_corset(spot, decision, api):
    if spot.street != 'river':
        return decision
    P, B = spot.pot, spot.to_call
    hole, board = spot.hole, spot.board
    act, amt = decision['action'], decision.get('amount', 0)

    # build the ONE villain range we score against: polarized betting range,
    # value sized to the bet, plus the size-correct bluff load.
    Rbet = villain_bet_range(api, board, B, P)

    # ---------- (a) CALL / call-an-allin discipline ----------
    if act == 'call' and B > 0:
        req = api.required_equity(B, P)          # 0.418 for 51 into 20
        E   = api.equity(hole, Rbet, board)      # our equity vs the bet
        if E < req - MARGIN and not _mdf_protected(api, hole, board, B, P):
            return {'action': 'fold', 'amount': 0}   # EV_call<0 -> EV_fold=0
        return decision                          # E>=req-margin: PERMITTED, no spew

    # ---------- (c) ALL-IN as pure EV (we shove or are pot-committed) ----------
    if act in ('bet','raise') and _is_allin(spot, amt):
        # treat our jam as +EV-only when called: need fold-equity or value
        cls = api.hand_class_of(api.hand_rank(hole, board))
        if cls not in VALUE_CLASSES and not _credible_bluff(spot, api, amt, P):
            return {'action': 'check', 'amount': 0}  # downgrade pure-spew jam
        return decision

    # ---------- (b) BET / OVERBET size cap + bluff:value bound ----------
    if act in ('bet','raise') and amt > 0:
        cls = api.hand_class_of(api.hand_rank(hole, board))
        is_value = cls in VALUE_CLASSES
        if amt > P:                              # overbet
            # GTO bound: allowed bluffs/value = B/(P+2B). If not value and
            # we exceed that bluff budget, demote size to <= pot.
            if not is_value and not _credible_bluff(spot, api, amt, P):
                amt = min(amt, int(round(0.66 * P)))
        decision['amount'] = _clamp_legal(amt, spot)
    return decision
```

Helpers (all on existing APIs):

```python
def villain_bet_range(api, board, B, P):
    # polarized: value = top combos that beat a bluff-catcher,
    #            bluffs loaded to GTO ratio B:(P+2B).
    bluff_frac = B / (P + 2*B)                    # = required_equity-ish weight
    value_frac = max(0.02, 0.25 * (P / (P+B)))    # tighter as bet grows
    return api.range_top(value_frac) | api.bluff_combos(board, bluff_frac)

def _mdf_protected(api, hole, board, B, P):
    # don't let the corset push hero's fold rate above 1-MDF:
    # protect hands inside the top MDF slice of OUR range.
    keep = api.mdf(B, P)                          # P/(P+B)
    return api.range_top(keep).contains(hole, board)

def _credible_bluff(spot, api, amt, P):
    t = api.board_texture(spot.board)
    return t.draw_heavy or api.range_top(0.10).contains(spot.hole, spot.board)
```

## 3. How NOT to over-fold

Three independent safeties:

1. **EV gate, not range gate.** We only fold when `E < req - MARGIN`. Any hand with `E ≥ req` is explicitly *permitted* (the corset returns `decision` unchanged). This is correct EV-based discipline from §4 Step C — it cannot fold a +EV call.
2. **MARGIN (0.03)** keeps genuinely breakeven/indifferent bluff-catchers in. Only clear losers are cut.
3. **MDF floor (`_mdf_protected`)** vs polarized overbets we still defend the top `MDF = P/(P+B)` slice of our own range even if the equity model is pessimistic, so villain can't auto-profit with any-two. The corset never folds a hand inside that slice.

Net: we cut the *bottom* (-EV) bluff-catchers facing overbets and keep enough range to satisfy MDF — eliminating spew without over-folding.

## 4. Grounded, deterministic A/B test

Replay is fully deterministic (fixed hole/board → fixed `equity`/`required_equity`).

```python
# tests/test_river_corset.py
SPOTS = load_logged_river_spots("logs/gtow_session.jsonl")  # the 100 river decisions

def test_corset_kills_overbet_spew():
    base = bb=0; corset = 0
    n_disaster_before = n_disaster_after = 0
    for s in SPOTS:
        d0 = brain.decide_spot(s)
        d1 = river_corset(s, dict(d0), api)
        ev0 = realized_bb(s, d0)        # from log result
        ev1 = realized_bb_counterfactual(s, d1)  # fold->0, else logged
        base   += ev0; corset += ev1
        req = api.required_equity(s.to_call, s.pot)
        E   = api.equity(s.hole, villain_bet_range(api,s.board,s.to_call,s.pot), s.board)
        if s.to_call > s.pot and E < req:           # the disaster pattern
            n_disaster_before += (d0['action']=='call')
            n_disaster_after  += (d1['action']=='call')

    assert n_disaster_after == 0                      # all -EV overbet calls folded
    assert (corset - base) >= 350                     # ~+40bb x ~10 hands
    # non-disaster spots unchanged:
    for s in SPOTS:
        if not (s.to_call > s.pot and api.equity(s.hole,
                villain_bet_range(api,s.board,s.to_call,s.pot), s.board) < api.required_equity(s.to_call,s.pot)):
            assert river_corset(s, dict(brain.decide_spot(s)), api) == brain.decide_spot(s)
```

Expected result: the ~10 overbet-call hands (`51 into 20`, `E≈0.30 < 0.418−0.03`) flip `call→fold` (each `−40bb → 0bb`, ≈ **+400bb** ≈ +94 bb/100 over the sample), `n_disaster_after == 0`, and the ~90 break-even hands are byte-identical pass-throughs (corset is a strict no-op when `E ≥ req − MARGIN`).