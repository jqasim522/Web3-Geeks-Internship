"""
rag_lib.py - shared infrastructure for the Week 4 Day 2 property knowledge layer.

Design
------
* EXECUTED path (works with stdlib + pandas only): TF-IDF cosine retriever,
  SQLite structured store, rule-based question parser, hybrid router,
  extractive (non-generative) answerer.
* REFERENCE path (needs network + pip): LangChain + ChromaDB + Gemini.
  `get_llm()` switches to Gemini automatically when GEMINI_API_KEY is set AND
  langchain_google_genai is importable. That branch has NOT been executed in
  the sandbox this repo was built in (no network, no key).

Nothing here fabricates data: every fact returned comes from a row in
data/realestate.db (built from the intern-provided CSV).
"""
import json
import math
import os
import re
import sqlite3
import statistics
import time
import logging
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "realestate.db")
BROCHURE_DIR = os.path.join(DATA_DIR, "brochures")

CITIES = ["Lahore", "Karachi", "Islamabad", "Rawalpindi"]
PROPERTY_TYPES = ["House", "Flat", "Commercial", "Farm House", "Studio", "Plot", "Portion", "Other"]

# --------------------------------------------------------------------------
# Amenity tags derived from listing text (the CSV has NO amenities column).
# Regexes run on lower-cased descriptions. Zero-hit tags (gym, security) are kept
# on purpose so questions about them get an honest "none of the listings say so".
# --------------------------------------------------------------------------
AMENITY_PATTERNS = {
    "swimming_pool": r"swimming|\bpool\b",
    "basement": r"basement",
    "furnished": r"\bfurnished\b|\bfurnishing\b",
    "corner": r"\bcorner\b",
    "park": r"\bpark\b(?!\s+view\s+city)",
    "lift": r"\blift\b|elevator",
    "solar": r"\bsolar\b",
    "servant_quarter": r"servant",
    "garden_lawn": r"\bgarden\b|\blawn\b",
    "sea_facing": r"sea[- ]?(facing|view)|facing sea|sea view",
    "home_theatre": r"theat(re|er)|cinema",
    "mosque": r"mosque|masjid",
    "school": r"\bschool\b",
    "gym": r"\bgym\b|gymnasium|fitness",
    "security": r"security|gated",
    "brand_new": r"brand[- ]new",
}
# words a user might say -> amenity tag
AMENITY_QUERY_TERMS = {
    "swimming_pool": ["pool", "swimming"], "basement": ["basement"], "furnished": ["furnished", "furnishing"],
    "corner": ["corner"], "park": ["park facing", "park"], "lift": ["lift", "elevator"], "solar": ["solar"],
    "servant_quarter": ["servant"], "garden_lawn": ["garden", "lawn"], "sea_facing": ["sea facing", "sea view"],
    "home_theatre": ["theatre", "theater", "cinema"], "mosque": ["mosque", "masjid"], "school": ["school"],
    "gym": ["gym", "gymnasium", "fitness"], "security": ["security", "gated"], "brand_new": ["brand new"],
}


def extract_amenities(text):
    t = str(text).lower()
    return [k for k, pat in AMENITY_PATTERNS.items() if re.search(pat, t)]


# --------------------------------------------------------------------------
# Price formatting (Pakistani convention)
# --------------------------------------------------------------------------
def format_price(p):
    p = float(p)
    if p < 100_000:
        return f"{p / 1000:.0f} thousand"
    if p < 10_000_000:
        return f"{p / 100_000:.2f} lac"
    return f"{p / 10_000_000:.2f} crore"


# --------------------------------------------------------------------------
# Tokenizer / TF-IDF (stdlib only)
# --------------------------------------------------------------------------
STOP = set("a an the of and or for in on at to is are with by from as it its this that be was were "
           "which what who how do does did any all me my your you i we there than show find list tell".split())


def _stem(t):
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


def tokenize(text):
    """Word tokens; hyphenated tokens (IDs like lah-0001, F-7) are kept whole AND split."""
    out = []
    for tok in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(text).lower()):
        parts = tok.split("-")
        cands = [tok] + parts if len(parts) > 1 else [tok]
        for c in cands:
            c = _stem(c)
            if c and c not in STOP:
                out.append(c)
    return out


class TfidfIndex:
    """Cosine TF-IDF over documents [{id, text, meta}]. Normalised (unlike the raw
    sum-of-tf*idf scorer in the assignment stub) so long chunks are not favoured
    simply for being long - important for a fair chunk-size comparison."""

    def __init__(self, docs):
        self.docs = docs
        n = len(docs)
        toks = [tokenize(d["text"]) for d in docs]
        df = Counter()
        for t in toks:
            df.update(set(t))
        self.idf = {w: math.log((1 + n) / (1 + c)) + 1.0 for w, c in df.items()}
        self.inv = defaultdict(list)
        for i, t in enumerate(toks):
            tf = Counter(t)
            vec = {w: (1 + math.log(c)) * self.idf[w] for w, c in tf.items()}
            norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
            for w, x in vec.items():
                self.inv[w].append((i, x / norm))

    def search(self, query, k=5, allowed_ids=None):
        qt = Counter(t for t in tokenize(query) if t in self.idf)
        if not qt:
            return []
        qv = {w: (1 + math.log(c)) * self.idf[w] for w, c in qt.items()}
        qn = math.sqrt(sum(x * x for x in qv.values())) or 1.0
        scores = defaultdict(float)
        for w, qx in qv.items():
            for i, dx in self.inv[w]:
                scores[i] += (qx / qn) * dx
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        out = []
        for i, s in ranked:
            d = self.docs[i]
            if allowed_ids is not None and d["id"] not in allowed_ids:
                continue
            out.append((s, d))
            if len(out) == k:
                break
        return out


def est_tokens(text):
    """~1.3 tokens per whitespace word (rough LLM-tokenizer proxy; no tokenizer download needed)."""
    return int(len(text.split()) * 1.3) + 1 if text.strip() else 0


def chunk_text(text, max_tokens, overlap_frac=0.10):
    """Greedy line-boundary chunker with ~10% overlap (in lines). A chunk never splits a listing line."""
    lines = [l for l in text.split("\n") if l.strip()]
    overlap_budget = int(max_tokens * overlap_frac)
    chunks, cur, cur_tok = [], [], 0
    for line in lines:
        t = est_tokens(line)
        if cur and cur_tok + t > max_tokens:
            chunks.append("\n".join(cur))
            keep, kt = [], 0
            for prev in reversed(cur):
                pt = est_tokens(prev)
                if kt + pt > overlap_budget:
                    break
                keep.insert(0, prev)
                kt += pt
            cur, cur_tok = keep, kt
        cur.append(line)
        cur_tok += t
    if cur:
        chunks.append("\n".join(cur))
    return chunks


# --------------------------------------------------------------------------
# SQLite
# --------------------------------------------------------------------------
def get_connection(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_property(pid, conn=None):
    """Fetch one property by ID. Returns dict or None.
    Catches DB-locked errors and returns None instead of crashing."""
    own = conn is None
    conn = conn or get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM properties WHERE property_id = ?", (pid.upper(),)
        ).fetchone()
    except sqlite3.OperationalError as e:
        logging.getLogger(__name__).warning("get_property db_locked: %s", e)
        if own:
            conn.close()
        return None
    if own:
        conn.close()
    return dict(row) if row else None

def query_properties(conn=None, city=None, area_like=None, property_type=None, bedrooms=None,
                     min_price=None, max_price=None, purpose=None, developer=None,
                     installment=None, order_by=None, limit=None):
    """Query properties with filters. ALWAYS returns a list (never None).

    Handles sqlite3.OperationalError (database locked) gracefully by
    returning an empty list, so callers can safely iterate the result.
    """
    own = conn is None
    conn = conn or get_connection()

    sql, args = "SELECT * FROM properties WHERE 1=1", []
    if city:
        sql += " AND city = ?"; args.append(city)
    if area_like:
        sql += " AND area LIKE ?"; args.append(f"%{area_like}%")
    if property_type:
        sql += " AND property_type = ?"; args.append(property_type)
    if bedrooms is not None:
        sql += " AND bedrooms = ?"; args.append(int(bedrooms))
    if min_price is not None:
        sql += " AND price_pkr >= ?"; args.append(int(min_price))
    if max_price is not None:
        sql += " AND price_pkr <= ?"; args.append(int(max_price))
    if purpose:
        sql += " AND lower(purpose) = lower(?)"; args.append(purpose)
    if developer:
        sql += " AND developer = ?"; args.append(developer)
    if installment is not None:
        sql += " AND has_installment_plan = ?"; args.append(1 if installment else 0)
    if order_by in ("price_pkr", "price_pkr DESC", "size_sqft", "size_sqft DESC"):
        sql += f" ORDER BY {order_by}"
    if limit:
        sql += f" LIMIT {int(limit)}"

    # Default result — ensures we ALWAYS return a list
    rows = []

    try:
        rows = [dict(r) for r in conn.execute(sql, args).fetchall()]
    except sqlite3.OperationalError as e:
        logging.getLogger(__name__).warning("query_properties db_locked: %s", e)
        rows = []
    except Exception as e:
        logging.getLogger(__name__).warning("query_properties error: %s", e)
        rows = []
    finally:
        if own:
            try:
                conn.close()
            except Exception:
                pass

    return rows  # <-- ALWAYS at the end, outside try/except/finally

# --------------------------------------------------------------------------
# Document loading (brochures + FAQs)
# --------------------------------------------------------------------------
def load_documents():
    docs = []
    for fn in sorted(os.listdir(BROCHURE_DIR)):
        if fn.endswith(".txt"):
            with open(os.path.join(BROCHURE_DIR, fn), encoding="utf-8") as f:
                docs.append({"id": fn[:-4], "text": f.read(), "meta": {"category": "brochure", "source": fn, "property_id": fn[:-4]}})
    faq_path = os.path.join(DATA_DIR, "faqs.csv")
    if os.path.exists(faq_path):
        import csv
        with open(faq_path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                docs.append({"id": r["faq_id"], "text": f"Q: {r['question']}\nA: {r['answer']}",
                             "meta": {"category": "faq", "source": "faqs.csv", "property_id": None}})
    return docs


# --------------------------------------------------------------------------
# Question parsing (rule-based; NOT an LLM)
# --------------------------------------------------------------------------
ID_RE = re.compile(r"\b(?:LAH|KAR|ISL|RAW)-\d{4}\b", re.I)
UNIT = {"crore": 10_000_000, "cr": 10_000_000, "lac": 100_000, "lakh": 100_000, "lacs": 100_000,
        "lakhs": 100_000, "million": 1_000_000, "billion": 1_000_000_000}
_MONEY = r"(\d+(?:\.\d+)?)\s*(crore|cr|lacs?|lakhs?|million|billion)\b"

INTENT_WORDS = ("property", "properties", "listing", "house", "flat", "apartment", "plot", "bungalow", "villa",
                "bedroom", "bed ", "bath", "price", "priced", "cost", "sale", "rent", "buy", "kanal", "marla",
                "sqft", "sq ft", "square", "developer", "installment", "instalment", "society", "phase",
                "cheapest", "expensive", "studio", "farm", "commercial", "pool", "basement", "furnished", "gym",
                "amenit", "area", "locality", "dha", "bahria", "listed",
                "home", "family", "school", "neighbo", "budget", "invest", "residential", "apartment", "location")


def in_scope(question):
    q = question.lower()
    return bool(ID_RE.search(question)) or any(w in q for w in INTENT_WORDS)


def parse_question(question):
    q = question.lower()
    p = {"ids": [m.upper() for m in ID_RE.findall(question)]}
    p["city"] = next((c for c in CITIES if c.lower() in q), None)
    p["property_type"] = None
    for pat, val in (("farm ?house", "Farm House"), (r"\bstudio", "Studio"), (r"\bflats?\b|apartment", "Flat"),
                     (r"\bcommercial", "Commercial"), (r"\bplots?\b", "Plot"), (r"\bportion", "Portion"),
                     (r"\bhouses?\b|bungalow|villa", "House")):
        if re.search(pat, q):
            p["property_type"] = val
            break
    m = re.search(r"(\d+)[- ]*(?:bed|bedroom)", q)
    p["bedrooms"] = int(m.group(1)) if m else None
    p["min_price"] = p["max_price"] = None
    m = re.search(r"between\s+" + _MONEY + r"\s+and\s+" + _MONEY, q)
    if m:
        p["min_price"] = int(float(m.group(1)) * UNIT[m.group(2)])
        p["max_price"] = int(float(m.group(3)) * UNIT[m.group(4)])
    else:
        m = re.search(r"(?:under|below|less than|cheaper than|up to|upto|within|max(?:imum)?)\s*(?:rs\.?\s*|pkr\s*)?" + _MONEY, q)
        if m:
            p["max_price"] = int(float(m.group(1)) * UNIT[m.group(2)])
        m = re.search(r"(?:above|over|more than|at least|min(?:imum)?)\s*(?:rs\.?\s*|pkr\s*)?" + _MONEY, q)
        if m:
            p["min_price"] = int(float(m.group(1)) * UNIT[m.group(2)])
    # area filter: substring match on the `area` column
    p["area_like"] = None
    for pat, val in ((r"\bdha\b|defence", "DHA"), (r"bahria", "Bahria"), (r"park view", "Park View"),
                     (r"\bf-?(6|7|8|10|11)\b", None), (r"clifton", "Clifton"), (r"gulberg", "Gulberg")):
        mm = re.search(pat, q)
        if mm:
            p["area_like"] = val if val else "F-" + mm.group(1)
            break
    # "developer" questions filter on the developer field, not the area text
    p["developer"] = None
    if re.search(r"developer|builder|developed by", q):
        for pat, val in ((r"park view", "Park View"), (r"bahria", "Bahria Town"), (r"\bdha\b", "DHA"), (r"paragon", "Paragon")):
            if re.search(pat, q):
                p["developer"], p["area_like"] = val, None
                break
    p["installment"] = True if re.search(r"instal?lments?|down payment", q) else None
    qa = re.sub(r"park view( city)?", " ", q)   # 'Park View' is a place name, not the park amenity
    p["amenities"] = [k for k, terms in AMENITY_QUERY_TERMS.items()
                      if any(re.search(r"\b" + re.escape(t) + r"\b", qa) for t in terms)]
    p["both"] = bool(re.search(r"\bboth\b|\band\b", q)) and len(p["amenities"]) > 1
    p["aggregate"] = None
    if re.search(r"average|mean", q):
        p["aggregate"] = "avg"
    elif re.search(r"median", q):
        p["aggregate"] = "median"
    elif re.search(r"how many|count|number of", q):
        p["aggregate"] = "count"
    elif re.search(r"cheapest|lowest|least expensive", q):
        p["aggregate"] = "min"
    elif re.search(r"most expensive|highest|priciest", q):
        p["aggregate"] = "max"
    if re.search(r"which developer|top developer|developer has the most|most listings", q):
        p["aggregate"] = "top_developer"
    p["attribute"] = None
    for attr, pat in (("bedrooms", r"bedroom|\bbeds?\b"), ("bathrooms", r"bathroom|\bbaths?\b"),
                      ("price_pkr", r"price|cost|priced|how much"), ("size_sqft", r"size|sq ?ft|square f"),
                      ("developer", r"developer|builder"), ("property_type", r"type of|what type|kind of"),
                      ("area", r"which area|what area|where|locality|located|neighbou?rhood")):
        if re.search(pat, q):
            p["attribute"] = attr
            break
    return p


# --------------------------------------------------------------------------
# Hybrid router (assignment stub, extended: IDs, numeric filters and aggregates are SQL signals)
# --------------------------------------------------------------------------
SQL_KEYWORDS = ["under", "below", "above", "over ", "bedroom", "city", "price", "cheaper", "cheapest",
                "expensive", "average", "how many", "count", "number of", "developer", "in lahore", "in karachi",
                "in islamabad", "in rawalpindi", "installment", "median"]
VECTOR_KEYWORDS = ["family", "feel", "describe", "amenities", "mention", "payment plan", "nearby",
                   "neighborhood", "neighbourhood", "pool", "basement", "furnished", "gym", "solar", "lift",
                   "corner", "sea", "theatre", "similar", "like", "features", "have a", "has a"]


def route_retrieval(question):
    q = question.lower()
    if ID_RE.search(question) or re.search(_MONEY, q):
        # exact identifiers / numeric filters -> SQL, unless narrative words are also present
        has_vec = any(k in q for k in VECTOR_KEYWORDS)
        return "hybrid" if (has_vec and not ID_RE.search(question)) else "sql"
    has_sql = any(k in q for k in SQL_KEYWORDS) or any(c.lower() in q for c in CITIES)
    has_vec = any(k in q for k in VECTOR_KEYWORDS)
    if has_sql and has_vec:
        return "hybrid"
    if has_sql:
        return "sql"
    if has_vec:
        return "vector"
    return "hybrid"


# --------------------------------------------------------------------------
# Extractive answerer (used when no Gemini key). Returns payload + text + sources.
# --------------------------------------------------------------------------
REFUSAL = ("I can only answer questions about the property listings in this knowledge base "
           "(Lahore, Karachi, Islamabad, Rawalpindi - sale listings), so I can't help with that.")


def _fmt_row(r):
    bed = f"{r['bedrooms']}-bed " if r.get("bedrooms") is not None else ""
    return f"{r['property_id']}: {bed}{r['property_type']} in {r['area']}, {r['city']} - {r['price_formatted']}"


def _filters_from_parse(p):
    return {k: p[k] for k in ("city", "property_type", "bedrooms", "min_price", "max_price", "area_like", "installment", "developer")
            if p.get(k) is not None}


def answer_question(question, index, conn=None, k=5, force_route=None):
    """Hybrid answerer. Returns dict(route, answer, sources, payload).
    payload['kind'] in value|count|aggregate|ids|none|not_found|not_recorded|refusal|passages."""
    own = conn is None
    conn = conn or get_connection()
    try:
        return _answer(question, index, conn, k, force_route)
    finally:
        if own:
            conn.close()


def _amenity_regex_match(row, amenities, both):
    tags = set(extract_amenities(row["description"]))
    hits = [a in tags for a in amenities]
    return all(hits) if both else any(hits)


def _answer(question, index, conn, k, force_route):
    if not in_scope(question):
        return {"route": "refuse", "answer": REFUSAL, "sources": [], "payload": {"kind": "refusal"}}
    route = force_route or route_retrieval(question)
    p = parse_question(question)

    # 1) exact ID lookups ---------------------------------------------------
    if p["ids"]:
        pid = p["ids"][0]
        row = get_property(pid, conn)
        if not row:
            return {"route": "sql", "answer": f"No listing with ID {pid} exists in the knowledge base.",
                    "sources": [], "payload": {"kind": "not_found", "id": pid}}
        attr = p["attribute"]
        if attr == "area":
            attr = "area"
        if attr in ("bedrooms", "bathrooms", "size_sqft", "price_pkr", "developer", "property_type", "area"):
            val = row[attr]
            if val is None:
                return {"route": "sql", "answer": f"{pid} does not have a recorded {attr} value in the listing.",
                        "sources": [pid], "payload": {"kind": "not_recorded", "id": pid, "field": attr}}
            shown = row["price_formatted"] + f" ({int(val):,} PKR)" if attr == "price_pkr" else val
            return {"route": "sql", "answer": f"{pid}: {attr} = {shown}.", "sources": [pid],
                    "payload": {"kind": "value", "id": pid, "field": attr, "value": val}}
        return {"route": "sql", "answer": _fmt_row(row), "sources": [pid],
                "payload": {"kind": "value", "id": pid, "field": "summary", "value": _fmt_row(row)}}

    filt = _filters_from_parse(p)

    # 2) aggregates ---------------------------------------------------------
    agg = p["aggregate"]
    if agg == "top_developer":
        rows = query_properties(conn, **{k2: v for k2, v in filt.items()})
        cnt = Counter(r["developer"] for r in rows if r["developer"] != "Private / Unknown")
        if not cnt:
            return {"route": "sql", "answer": "No named developer found for that filter.", "sources": [],
                    "payload": {"kind": "none"}}
        dev, n = cnt.most_common(1)[0]
        ids = [r["property_id"] for r in rows if r["developer"] == dev]
        return {"route": "sql", "answer": f"{dev} has the most listings ({n}) among named developers"
                                          f" for this filter (excluding 'Private / Unknown').",
                "sources": ids, "payload": {"kind": "aggregate", "op": "top_developer", "value": dev, "n": n,
                                             "filters": filt}}
    if agg in ("avg", "median", "count", "min", "max"):
        rows = query_properties(conn, **filt)
        if p["amenities"]:
            rows = [r for r in rows if _amenity_regex_match(r, p["amenities"], p["both"])]
        if not rows:
            return {"route": "sql", "answer": "No listings match that filter.", "sources": [],
                    "payload": {"kind": "none", "filters": filt}}
        ids = [r["property_id"] for r in rows]
        prices = [r["price_pkr"] for r in rows]
        if agg == "count":
            return {"route": route, "answer": f"{len(rows)} listings match.", "sources": ids,
                    "payload": {"kind": "count", "value": len(rows), "filters": filt}}
        if agg == "avg":
            v = sum(prices) / len(prices)
        elif agg == "median":
            v = statistics.median(prices)
        elif agg == "min":
            best = min(rows, key=lambda r: r["price_pkr"]); v = best["price_pkr"]
        else:
            best = max(rows, key=lambda r: r["price_pkr"]); v = best["price_pkr"]
        if agg in ("min", "max"):
            return {"route": "sql", "answer": f"{'Cheapest' if agg == 'min' else 'Most expensive'}: {_fmt_row(best)}"
                                              f" (among {len(rows)} matching listings).",
                    "sources": ids,
                    "payload": {"kind": "aggregate", "op": agg, "value": v, "id": best["property_id"], "n": len(rows),
                                "filters": filt}}
        return {"route": "sql", "answer": f"{agg.capitalize()} price over {len(rows)} listings: {format_price(v)} ({int(v):,} PKR).",
                "sources": ids, "payload": {"kind": "aggregate", "op": agg, "value": v, "n": len(rows), "filters": filt}}

    # 3) amenity / 'mentions' questions: SQL filter first, then verify against the description text
    if p["amenities"]:
        rows = query_properties(conn, **filt)
        hits = [r for r in rows if _amenity_regex_match(r, p["amenities"], p["both"])]
        label = (" and " if p["both"] else " or ").join(p["amenities"])
        if not hits:
            return {"route": "hybrid", "answer": f"None of the {len(rows)} listings matching the filter mention: {label}.",
                    "sources": [], "payload": {"kind": "none", "amenities": p["amenities"], "filters": filt,
                                               "checked": len(rows)}}
        return {"route": "hybrid", "answer": f"{len(hits)} listing(s) mention {label}: " + "; ".join(_fmt_row(r) for r in hits[:10])
                                             + (" ..." if len(hits) > 10 else ""),
                "sources": [r["property_id"] for r in hits],
                "payload": {"kind": "ids", "ids": [r["property_id"] for r in hits], "amenities": p["amenities"],
                            "both": p["both"], "filters": filt}}

    # 4) plain structured search (filters only)
    if filt and route in ("sql", "hybrid") and any(k2 in filt for k2 in ("bedrooms", "min_price", "max_price", "installment")):
        rows = query_properties(conn, **filt, order_by="price_pkr", limit=200)
        if not rows:
            return {"route": route, "answer": "No listings match that filter.", "sources": [],
                    "payload": {"kind": "none", "filters": filt}}
        return {"route": route, "answer": f"{len(rows)} listings match; cheapest 5: " + "; ".join(_fmt_row(r) for r in rows[:5]),
                "sources": [r["property_id"] for r in rows],
                "payload": {"kind": "ids", "ids": [r["property_id"] for r in rows], "filters": filt}}

    # 5) semantic search over brochures + FAQs (optionally restricted by SQL-filtered ids)
    allowed = None
    if filt:
        allowed = {r["property_id"] for r in query_properties(conn, **filt)} | {d["id"] for d in index.docs if d["meta"]["category"] == "faq"}
    results = index.search(question, k=k, allowed_ids=allowed)
    results = [(s, d) for s, d in results if s >= 0.15]
    if not results:
        return {"route": route, "answer": "I couldn't find anything in the knowledge base that answers that.",
                "sources": [], "payload": {"kind": "none"}}
    lines = [f"[{d['id']}] {d['text'].splitlines()[-1][:160]}" for s, d in results]
    return {"route": route, "answer": "Closest matches: " + " | ".join(lines), "sources": [d["id"] for s, d in results],
            "payload": {"kind": "passages", "ids": [d["id"] for s, d in results], "scores": [round(s, 3) for s, d in results]}}


# --------------------------------------------------------------------------
# LLM shim: real Gemini if key + package available, otherwise offline extractive stand-in
# --------------------------------------------------------------------------
class OfflineExtractiveLLM:
    """No generation: the answerer above returns fields straight from retrieved rows."""
    name = "offline-extractive (no LLM)"


def get_llm():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return OfflineExtractiveLLM()
    try:  # REFERENCE PATH - not executed in the build sandbox
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                                      google_api_key=key, temperature=0)
    except Exception as e:  # package missing / network blocked
        print(f"[rag_lib] Gemini unavailable ({type(e).__name__}); using offline extractive mode")
        return OfflineExtractiveLLM()


def safe_llm_call(llm, prompt, delay=5):
    """Sleep-before-call throttle (5 s per project instructions; the assignment stub used 2 s)."""
    time.sleep(delay)
    return llm.invoke(prompt)


def call_with_retry(llm, prompt, attempts=5, min_wait=2, max_wait=30):
    """Exponential backoff. Uses tenacity if installed; otherwise a stdlib loop with identical behaviour."""
    try:
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(stop=stop_after_attempt(attempts), wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait))
        def _call():
            return safe_llm_call(llm, prompt)
        return _call()
    except ImportError:
        wait = min_wait
        for i in range(attempts):
            try:
                return safe_llm_call(llm, prompt)
            except Exception:
                if i == attempts - 1:
                    raise
                time.sleep(wait)
                wait = min(wait * 2, max_wait)
