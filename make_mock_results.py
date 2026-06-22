#!/usr/bin/env python3
"""Generate mock workshop results matching the `fetch_results.py` schema.

Produces `results_mock.csv` with the exact 2x2 workshop scope so the phase-2
aggregation/summary pipeline can be built and tested before real data exists:

    techniques     : rlhf, ai_debate
    failure modes  : jailbreaking, deceptive_alignment

Structure modelled (so the pipeline exercises every dimension):
  * N participants, each with a stable `personal_id` across BOTH rounds, so
    round1 -> round2 individual change is trackable.
  * `group_id` is written ONLY in round 2 (matches the app), enabling
    group-level aggregation.
  * Realistic signal: techniques reduce risk more for jailbreaking than for
    deceptive alignment (which gets some negative draws), and round 2 converges
    toward each group's round-1 consensus with tighter CIs / higher confidence
    (the IDEA/Delphi effect the phase-2 summary should reveal).

Deterministic (seeded). Re-run to regenerate. Tweak N_PARTICIPANTS / BASELINES.
"""

import csv
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results_mock.csv"
SEED = 20260624
N_PARTICIPANTS = 12
N_GROUPS = 3

COLUMNS = [
    "personal_id", "round", "group_id", "affiliation", "role", "years_experience",
    "failure_mode_id", "technique_id", "point_estimate", "lower_bound",
    "upper_bound", "confidence", "rationale", "created_at",
]

FAILURE_MODES = ["jailbreaking", "deceptive_alignment"]
TECHNIQUES = ["rlhf", "ai_debate"]

# "True" central effect (% risk reduction vs SFT baseline; higher = better) and a
# floor for clipping. Deceptive alignment is hard -> low means, negatives allowed.
BASELINES = {
    ("jailbreaking", "rlhf"): dict(mu=18, floor=0, cap=60),
    ("jailbreaking", "ai_debate"): dict(mu=15, floor=0, cap=60),
    ("deceptive_alignment", "rlhf"): dict(mu=8, floor=-30, cap=45),
    ("deceptive_alignment", "ai_debate"): dict(mu=12, floor=-30, cap=45),
}

AFFILIATIONS = [
    "Academia / University", "Industry / Company", "Government / Public sector",
    "Nonprofit / Civil society", "Independent / Other",
]
ROLES = [
    "Theoretical AI Safety Researcher", "Mechanistic Interpretability Researcher",
    "Scalable Oversight Researcher", "Applied ML Researcher",
    "AI Safety Policy / Governance", "Biosecurity / Dual-use Expert", "Other",
]
EXPERIENCE = ["<1", "1-2", "3-5", "6-9", "10+"]

# Short, plausible rationale pools keyed by failure mode.
RATIONALES = {
    "jailbreaking": [
        "Behavioral shaping catches most surface attacks but transfers poorly to novel jailbreak templates.",
        "Helps against known attack patterns; long-tail prompt injections remain.",
        "Reduces obvious misuse, though determined red-teamers still find gaps.",
        "Adversarial scrutiny of outputs raises the bar for elicitation attacks.",
        "Decent coverage on direct requests; multi-turn obfuscation is harder to block.",
    ],
    "deceptive_alignment": [
        "Does not intervene on latent mesa-objectives, so strategic deception can persist.",
        "Shapes behavior under observation but not the eval/deployment context switch.",
        "Adds output-level checks, not direct access to the model's internal objective.",
        "Unlikely to remove deceptive planning circuitry; may just teach better hiding.",
        "Limited leverage on situational awareness driving the deception.",
    ],
}


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def make_participants(rng):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I/O/0/1
    seen = set()
    people = []
    for i in range(N_PARTICIPANTS):
        while True:
            pid = "".join(rng.choice(alphabet) for _ in range(5))
            if pid not in seen:
                seen.add(pid)
                break
        people.append({
            "personal_id": pid,
            "group_id": (i % N_GROUPS) + 1,  # assigned at discussion; written round 2 only
            "affiliation": rng.choice(AFFILIATIONS),
            "role": rng.choice(ROLES),
            "years_experience": rng.choice(EXPERIENCE),
        })
    return people


def round1_estimate(rng, fm, tech):
    spec = BASELINES[(fm, tech)]
    est = round(clip(rng.gauss(spec["mu"], 11), spec["floor"], spec["cap"]))
    lower = round(clip(est - rng.uniform(8, 20), spec["floor"] - 10, est))
    upper = round(clip(est + rng.uniform(10, 30), est, spec["cap"] + 15))
    confidence = rng.choice([1, 2, 2, 3, 3])  # round 1: lower confidence
    return est, lower, upper, confidence


def main():
    rng = random.Random(SEED)
    people = make_participants(rng)

    # ---- Round 1: independent individual estimates -------------------------
    r1 = {}  # (pid, fm, tech) -> (est, lower, upper, conf)
    for p in people:
        for fm in FAILURE_MODES:
            for tech in TECHNIQUES:
                r1[(p["personal_id"], fm, tech)] = round1_estimate(rng, fm, tech)

    # ---- Group consensus from round 1 (mean point estimate per cell) -------
    group_mean = {}
    for g in range(1, N_GROUPS + 1):
        members = [p["personal_id"] for p in people if p["group_id"] == g]
        for fm in FAILURE_MODES:
            for tech in TECHNIQUES:
                vals = [r1[(pid, fm, tech)][0] for pid in members]
                group_mean[(g, fm, tech)] = sum(vals) / len(vals)

    # ---- Round 2: revise toward group consensus, tighten, more confident ---
    rows = []
    t1 = "2026-06-24T09:{:02d}:00+00:00"
    t2 = "2026-06-24T14:{:02d}:00+00:00"
    for idx, p in enumerate(people):
        pid, g = p["personal_id"], p["group_id"]
        for fm in FAILURE_MODES:
            for tech in TECHNIQUES:
                spec = BASELINES[(fm, tech)]

                # round 1 row (no group_id yet)
                est, lo, hi, conf = r1[(pid, fm, tech)]
                rows.append(dict(
                    personal_id=pid, round=1, group_id="",
                    affiliation=p["affiliation"], role=p["role"],
                    years_experience=p["years_experience"],
                    failure_mode_id=fm, technique_id=tech,
                    point_estimate=est, lower_bound=lo, upper_bound=hi,
                    confidence=conf, rationale=rng.choice(RATIONALES[fm]),
                    created_at=t1.format(idx),
                ))

                # round 2 row: 55% own / 45% group consensus + small noise
                gm = group_mean[(g, fm, tech)]
                est2 = round(clip(0.55 * est + 0.45 * gm + rng.gauss(0, 3),
                                  spec["floor"], spec["cap"]))
                lo2 = round(clip(est2 - rng.uniform(5, 12), spec["floor"] - 5, est2))
                hi2 = round(clip(est2 + rng.uniform(6, 16), est2, spec["cap"] + 10))
                conf2 = clip(conf + rng.choice([0, 1, 1, 2]), 1, 5)
                rows.append(dict(
                    personal_id=pid, round=2, group_id=g,
                    affiliation=p["affiliation"], role=p["role"],
                    years_experience=p["years_experience"],
                    failure_mode_id=fm, technique_id=tech,
                    point_estimate=est2, lower_bound=lo2, upper_bound=hi2,
                    confidence=conf2, rationale=rng.choice(RATIONALES[fm]),
                    created_at=t2.format(idx),
                ))

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows ({N_PARTICIPANTS} participants x 2 rounds x "
          f"{len(FAILURE_MODES) * len(TECHNIQUES)} cells) -> {OUT}")


if __name__ == "__main__":
    main()
