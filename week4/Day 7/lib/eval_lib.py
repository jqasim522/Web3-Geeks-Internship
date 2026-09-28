"""
eval_lib.py - Task 5 hallucination evaluation.

* Ground truth is computed with plain pandas straight from data/properties_normalized.csv
  (a different code path from the SQLite/rule-parser system under test).
* Every answer carries a structured payload; the verifier re-fetches each cited row and checks
  each claim against it (grounded / hallucinated), independent of the correctness check.
* CAVEAT (also in the report): the offline answerer is extractive and rule-based, and the 20
  questions were written alongside it. This measures retrieval + grounding of THIS pipeline,
  not the behaviour of a generative LLM.
"""
import json
import os
import random
import re

import pandas as pd

import rag_lib as r

DF = pd.read_csv(os.path.join(r.DATA_DIR, "properties_normalized.csv"))


def _has(df, pat):
    return df.description.str.contains(pat, case=False, regex=True)


def build_questions():
    rng = random.Random(7)  # ids for F2-F4 fixed by seed before any run
    kar = DF[(DF.city == "Karachi") & DF.bathrooms.notna()].property_id.tolist()
    isl = DF.property_id[DF.city == "Islamabad"].tolist()
    raw_ = DF.property_id[DF.city == "Rawalpindi"].tolist()
    f2, f3, f4 = rng.choice(kar), rng.choice(isl), rng.choice(raw_)
    row = lambda pid: DF[DF.property_id == pid].iloc[0]
    Q = []

    def add(cat, q, exp, src=None):
        Q.append({"id": f"Q{len(Q)+1}", "category": cat, "question": q, "expected": exp, "expected_sources": src or []})

    add("factual", "How many bedrooms does LAH-0001 have?", {"kind": "value", "value": int(row("LAH-0001").bedrooms)}, ["LAH-0001"])
    add("factual", f"How many bathrooms does {f2} have?", {"kind": "value", "value": int(row(f2).bathrooms)}, [f2])
    add("factual", f"What is the size in sqft of {f3}?", {"kind": "value", "value": int(row(f3).size_sqft)}, [f3])
    add("factual", f"What type of property is {f4}?", {"kind": "value", "value": row(f4).property_type}, [f4])
    add("factual", "How many bedrooms does LAH-0043 have?", {"kind": "not_recorded"}, ["LAH-0043"])  # NaN bedrooms (studio)

    add("pricing", "What is the price of LAH-0004?", {"kind": "value", "value": int(row("LAH-0004").price_pkr)}, ["LAH-0004"])
    d = DF[(DF.city == "Lahore") & DF.area.str.contains("DHA")]
    add("pricing", "What is the average price of listings in Lahore in areas whose name contains DHA?",
        {"kind": "aggregate", "op": "avg", "value": float(d.price_pkr.mean())}, d.property_id.tolist())
    d = DF[(DF.city == "Rawalpindi") & (DF.property_type == "House") & (DF.price_pkr <= 30_000_000)]
    add("pricing", "How many houses under 3 crore are listed in Rawalpindi?", {"kind": "count", "value": len(d)}, d.property_id.tolist())
    d = DF[(DF.city == "Karachi") & (DF.property_type == "Flat")]
    add("pricing", "What is the cheapest flat in Karachi?", {"kind": "aggregate", "op": "min", "value": int(d.price_pkr.min())},
        d.property_id[d.price_pkr == d.price_pkr.min()].tolist())
    d = DF[DF.city == "Islamabad"]
    add("pricing", "What is the most expensive listing in Islamabad?", {"kind": "aggregate", "op": "max", "value": int(d.price_pkr.max())},
        d.property_id[d.price_pkr == d.price_pkr.max()].tolist())

    d = DF[DF.developer == "Park View"]
    add("developer", "How many listings have Park View as the developer?", {"kind": "count", "value": len(d)}, d.property_id.tolist())
    d = DF[DF.has_installment_plan]
    add("developer", "How many listings have an installment plan?", {"kind": "count", "value": len(d)}, d.property_id.tolist())
    add("developer", "Which Karachi listings mention a gym?", {"kind": "none"}, [])
    d = DF[(DF.city == "Rawalpindi") & (DF.developer != "Private / Unknown")]
    top = d.developer.value_counts().index[0]
    add("developer", "Which developer has the most listings in Rawalpindi?", {"kind": "aggregate", "op": "top_developer", "value": top},
        d.property_id[d.developer == top].tolist())
    add("developer", "Who is the developer of LAH-9999?", {"kind": "not_found"}, [])

    d = DF[(DF.city == "Islamabad") & _has(DF, r"\bpool\b|swimming")]
    add("amenity", "Which Islamabad properties have a pool?", {"kind": "ids", "ids": sorted(d.property_id)}, d.property_id.tolist())
    d = DF[(DF.city == "Karachi") & _has(DF, "basement")]
    add("amenity", "Which Karachi listings have a basement?", {"kind": "ids", "ids": sorted(d.property_id)}, d.property_id.tolist())
    d = DF[(DF.city == "Lahore") & _has(DF, r"\bpool\b|swimming") & _has(DF, "basement")]
    add("amenity", "Which Lahore listings mention both a swimming pool and a basement?", {"kind": "ids", "ids": sorted(d.property_id)}, d.property_id.tolist())

    add("out_of_scope", "What's the weather in Lahore?", {"kind": "refusal"})
    add("out_of_scope", "Who won the last cricket world cup?", {"kind": "refusal"})
    return Q


# ---------------- correctness (vs pandas ground truth) ----------------
def is_correct(payload, exp):
    k = exp["kind"]
    if payload.get("kind") != k:
        return False
    if k == "value":
        return payload["value"] == exp["value"]
    if k == "count":
        return payload["value"] == exp["value"]
    if k == "aggregate":
        if payload.get("op") != exp["op"]:
            return False
        if exp["op"] == "top_developer":
            return payload["value"] == exp["value"]
        return abs(payload["value"] - exp["value"]) < 1
    if k == "ids":
        return sorted(payload["ids"]) == exp["ids"]
    return True  # none / not_found / not_recorded / refusal: kind match is enough


# ---------------- claim verification (grounded / hallucinated) ----------------
def row_satisfies(row, filt, amenities=None, both=False):
    if filt.get("city") and row["city"] != filt["city"]: return False
    if filt.get("area_like") and filt["area_like"].lower() not in row["area"].lower(): return False
    if filt.get("property_type") and row["property_type"] != filt["property_type"]: return False
    if filt.get("bedrooms") is not None and row["bedrooms"] != filt["bedrooms"]: return False
    if filt.get("min_price") is not None and row["price_pkr"] < filt["min_price"]: return False
    if filt.get("max_price") is not None and row["price_pkr"] > filt["max_price"]: return False
    if filt.get("developer") and row["developer"] != filt["developer"]: return False
    if filt.get("installment") is not None and bool(row["has_installment_plan"]) != bool(filt["installment"]): return False
    if amenities:
        tags = set(r.extract_amenities(row["description"]))
        ok = [a in tags for a in amenities]
        if not (all(ok) if both else any(ok)): return False
    return True


def verify(result, conn):
    """Returns (grounded, hallucinated, note). Re-fetches every cited row and checks each claim."""
    pl, src = result["payload"], result["sources"]
    k = pl["kind"]
    # any property id mentioned in the answer text must exist
    for m in set(r.ID_RE.findall(result["answer"])):
        if not r.get_property(m, conn):
            if k != "not_found":
                return False, True, f"answer mentions non-existent id {m}"
    rows = {s: r.get_property(s, conn) for s in src}
    if k == "refusal":
        return True, False, "no claim made"
    if k == "not_found":
        return (r.get_property(pl["id"], conn) is None), (r.get_property(pl["id"], conn) is not None), "absence checked"
    if k == "not_recorded":
        row = r.get_property(pl["id"], conn)
        ok = row is not None and row[pl["field"]] is None
        return ok, not ok, "NULL confirmed" if ok else "field is not NULL"
    if k == "value":
        row = rows.get(pl["id"])
        if row is None: return False, False, "cited row missing"
        if pl["field"] == "summary": return True, False, ""
        ok = row[pl["field"]] == pl["value"]
        return ok, not ok, "" if ok else "value differs from row"
    if k == "passages":
        faq_ids = {x[0] for x in conn.execute("SELECT faq_id FROM faqs").fetchall()}
        ok = all((s in faq_ids) or (rows.get(s) is not None) for s in src)
        return ok, not ok, "cited passage ids exist" if ok else "cited passage id unknown"
    rows = {s_: v for s_, v in rows.items()}
    if k != "passages" and any(v is None for v in rows.values()):
        return False, True, "cited id not in DB"
    filt = pl.get("filters", {})
    if k == "count":
        ok = pl["value"] == len(src) and all(row_satisfies(x, filt, pl.get("amenities"), pl.get("both", False)) for x in rows.values())
        return ok, not ok, ""
    if k == "ids":
        ok = all(row_satisfies(x, filt, pl.get("amenities"), pl.get("both", False)) for x in rows.values())
        return ok, not ok, "" if ok else "cited row does not satisfy the claim"
    if k == "aggregate":
        prices = [x["price_pkr"] for x in rows.values()]
        op = pl["op"]
        if op == "avg": ok = abs(sum(prices) / len(prices) - pl["value"]) < 1
        elif op == "median":
            import statistics; ok = abs(statistics.median(prices) - pl["value"]) < 1
        elif op == "min": ok = min(prices) == pl["value"]
        elif op == "max": ok = max(prices) == pl["value"]
        elif op == "top_developer":
            ok = all(x["developer"] == pl["value"] for x in rows.values()) and len(rows) == pl["n"]
        else: ok = False
        ok = ok and all(row_satisfies(x, filt) for x in rows.values())
        return ok, not ok, ""
    if k == "none":
        # absence claim: full scan of the DB with the python predicate
        all_rows = r.query_properties(conn)
        bad = [x["property_id"] for x in all_rows if row_satisfies(x, pl.get("filters", {}), pl.get("amenities"), pl.get("both", False))]
        return (not bad), bool(bad), f"{len(bad)} rows actually match" if bad else "full scan confirms none"
    return False, False, "unverified kind"


def run_eval(index, tag):
    conn = r.get_connection()
    Q = build_questions()
    rows = []
    for q in Q:
        res = r.answer_question(q["question"], index, conn)
        correct = is_correct(res["payload"], q["expected"])
        grounded, halluc, note = verify(res, conn)
        exp_src = set(q["expected_sources"])
        if exp_src:
            got = set(res["sources"])
            recall = len(exp_src & got) / len(exp_src)
            hit = recall == 1.0
        else:
            recall, hit = None, None
        rows.append({"id": q["id"], "category": q["category"], "question": q["question"], "route": res["route"],
                     "answer": res["answer"], "source_rows": res["sources"][:12] + (["..."] if len(res["sources"]) > 12 else []),
                     "n_sources": len(res["sources"]), "expected": q["expected"], "payload_kind": res["payload"]["kind"],
                     "grounded": grounded, "correct": correct, "hallucinated": halluc, "verify_note": note,
                     "retrieval_hit": hit, "retrieval_recall": recall})
    conn.close()
    n = len(rows)
    inscope = [x for x in rows if x["category"] != "out_of_scope"]
    oos = [x for x in rows if x["category"] == "out_of_scope"]
    rt = [x for x in rows if x["retrieval_hit"] is not None]
    m = {"tag": tag, "n_questions": n, "n_listings": int(len(DF)),
         "grounding_rate": sum(x["grounded"] for x in rows) / n,
         "correctness_rate": sum(x["correct"] for x in rows) / n,
         "hallucination_rate": sum(x["hallucinated"] for x in rows) / n,
         "retrieval_accuracy": sum(x["retrieval_hit"] for x in rt) / len(rt), "retrieval_n": len(rt),
         "mean_retrieval_recall": sum(x["retrieval_recall"] for x in rt) / len(rt),
         "refusal_rate": sum(x["correct"] for x in oos) / len(oos), "oos_n": len(oos),
         "correct_inscope": sum(x["correct"] for x in inscope), "n_inscope": len(inscope)}
    out = {"metrics": m, "rows": rows}
    json.dump(out, open(os.path.join(r.ROOT, "results", f"eval_{tag}.json"), "w"), indent=2, default=str)
    return out


# ---------------- pure-vector stress test ----------------
def vector_only_answer(question, index):
    """Retrieve top-5 passages with TF-IDF only (no SQL) and read the answer out of the passage text.
    Deliberately cautious reader: says 'not stated' rather than guessing."""
    hits = index.search(question, k=5)
    texts = [(d["id"], d["text"]) for s, d in hits]
    q = question.lower()
    if not hits:
        return "not retrievable", [], "refused"
    top_id, top_text = texts[0]
    ids_in_q = [m.upper() for m in r.ID_RE.findall(question)]
    if ids_in_q:
        target = next(((i, t) for i, t in texts if i == ids_in_q[0]), None)
        if target is None:
            return "target listing not in top-5 passages", [t[0] for t in texts], "refused"
        tid, ttxt = target
        if re.search(r"bedroom", q):
            m = re.search(r"(\d+)\s*bed\b", ttxt); return (m.group(1) if m else "not stated in passage"), [tid], ("answered" if m else "refused")
        if re.search(r"bathroom", q):
            m = re.search(r"(\d+)\s*bath\b", ttxt); return (m.group(1) if m else "not stated in passage"), [tid], ("answered" if m else "refused")
        if re.search(r"price", q):
            m = re.search(r"(?:rs\.?\s*|pkr\s*)(\d[\d,]*)|(\d+(?:\.\d+)?)\s*(crore|lac|lakh)", ttxt, re.I)
            return (m.group(0) if m else "price not stated in passage"), [tid], ("answered" if m else "refused")
        if re.search(r"size|sq", q):
            return "size in sqft not stated (passage gives marla/kanal/yards only)", [tid], "refused"
        m = re.search(r"Property type:\s*(.+)", ttxt); return (m.group(1) if m else "not stated"), [tid], ("answered" if m else "refused")
    return "cannot compute an aggregate/list from 5 passages", [t[0] for t in texts], "refused"


def run_stress(index):
    Q = [q for q in build_questions() if q["category"] in ("factual", "pricing")]
    out = []
    for q in Q:
        ans, src, status = vector_only_answer(q["question"], index)
        exp = q["expected"]
        if status == "answered" and exp["kind"] == "value":
            correct = str(ans).strip().lower() == str(exp["value"]).lower()
        else:
            correct = False
        outcome = "correct" if correct else ("refused/not answerable" if status == "refused" else "WRONG")
        top1 = index.search(q["question"], k=1)
        out.append({"id": q["id"], "question": q["question"], "vector_only_answer": ans, "expected": exp.get("value", exp["kind"]),
                    "target_in_top5": bool(set(q["expected_sources"]) & set(src)) if q["expected_sources"] else None,
                    "outcome": outcome})
    json.dump(out, open(os.path.join(r.ROOT, "results", "vector_only_stress_test.json"), "w"), indent=2, default=str)
    return out


# ---------------- adversarial / paraphrase probes (NOT part of the 20-question suite) ----------------
def build_probes():
    D = DF
    P = []
    def add(q, exp, note): P.append({"question": q, "expected": exp, "note": note})
    add("how many bed does lah-0001 have", {"kind": "value", "value": 6}, "lower-case ID, 'bed' wording")
    add("Price of KAR-0230 in PKR?", {"kind": "value", "value": int(D[D.property_id == "KAR-0230"].price_pkr.iloc[0])}, "terse phrasing")
    d = D[(D.city == "Karachi") & (D.bedrooms == 4) & (D.property_type == "House") & (D.price_pkr <= 50_000_000)]
    add("Show me 4 bedroom houses in Karachi below 5 crore", {"kind": "ids", "ids": sorted(d.property_id)}, "multi-filter list")
    add("Any rental apartments in Lahore?", {"kind": "none"}, "dataset has no rentals - should say none, not show sale listings")
    add("Is there a flat with a gym in Islamabad?", {"kind": "none"}, "zero-hit amenity")
    d = D[(D.city == "Rawalpindi") & (D.property_type == "House")]
    add("Cheapest house in Rawalpindi", {"kind": "aggregate", "op": "min", "value": int(d.price_pkr.min())}, "no 'what is'")
    add("What's the median price in Karachi?", {"kind": "aggregate", "op": "median", "value": float(D[D.city == "Karachi"].price_pkr.median())}, "median aggregate")
    d = D[(D.city == "Islamabad") & (D.bedrooms == 5) & (D.property_type == "House")]
    add("average price in Islamabad for 5 bedroom houses", {"kind": "aggregate", "op": "avg", "value": float(d.price_pkr.mean())}, "avg + beds + type")
    add("How many flats are there in Lahore?", {"kind": "count", "value": int(((D.city == "Lahore") & (D.property_type == "Flat")).sum())}, "count phrasing")
    d = D[(D.city == "Lahore") & D.description.str.contains(r"\blift\b|elevator", case=False)]
    add("Which Lahore listings have a lift?", ({"kind": "ids", "ids": sorted(d.property_id)} if len(d) else {"kind": "none"}), "amenity synonym (no Lahore lift listings exist)")
    add("Who is the CEO of Bahria Town?", {"kind": "refusal"}, "out-of-scope but contains an in-scope keyword")
    add("Is F-7 in Islamabad a safe neighbourhood?", {"kind": "refusal_or_none"}, "not in data (no safety info) - must not invent")
    add("What is the price of LAH-0004 in US dollars?", {"kind": "refusal_or_none"}, "no FX data - must not invent a conversion")
    add("Which houses in Lahore have a pool?", {"kind": "ids", "ids": sorted(D[(D.city == "Lahore") & (D.property_type == "House") & D.description.str.contains(r"\bpool\b|swimming", case=False)].property_id)}, "'houses' + pool")
    return P


def run_probes(index):
    conn = r.get_connection()
    out = []
    for p in build_probes():
        res = r.answer_question(p["question"], index, conn)
        exp = p["expected"]
        if exp["kind"] == "refusal_or_none":
            ok = res["payload"]["kind"] in ("refusal", "none", "not_found")
        elif exp["kind"] == "aggregate" and exp["op"] == "median":
            ok = res["payload"]["kind"] == "aggregate" and res["payload"].get("op") == "median" and abs(res["payload"]["value"] - exp["value"]) < 1
        else:
            ok = is_correct(res["payload"], exp)
        g, h, note = verify(res, conn)
        out.append({"question": p["question"], "note": p["note"], "answer": res["answer"][:140], "payload_kind": res["payload"]["kind"],
                    "correct": ok, "grounded": g, "hallucinated": h})
    conn.close()
    json.dump(out, open(os.path.join(r.ROOT, "results", "adversarial_probes.json"), "w"), indent=2, default=str)
    return out
