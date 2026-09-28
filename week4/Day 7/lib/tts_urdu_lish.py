"""
tts_urdu_lish.py - UrduLish text handling for the voice pipeline.

Two halves:

1. ``normalize_transcript``  (STT -> retrieval): STT for Urdu returns Urdu-script words, Roman-Urdu
   or Latin English. The Day-2 retriever/parser only understands Latin English tokens
   ("3 bedroom house Lahore under 3 crore", "LAH-0004"). This maps a *small, hand-written* lexicon
   of domain words to those tokens. It is NOT a general transliterator; unknown words pass through.

2. ``prepare_for_tts`` / ``render_reply`` (facts -> speech): builds short UrduLish replies from
   Day-2 payloads using templates (zero-LLM path) and rewrites tokens that TTS engines read badly
   (prices, property IDs, acronyms, sector codes such as F-7).

Nothing here was verified by listening to audio. The phonetic-hint table is a set of *untested
candidates*, disabled by default; see ``scripts/tts_pronunciation_test.py`` for the human review flow.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("voice.urdu")

# --------------------------------------------------------------------------------------
# Lexicons (hand-written, deliberately small)
# --------------------------------------------------------------------------------------
ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Urdu-script -> canonical Latin token(s). Multi-word keys are matched first (longest first).
URDU_SCRIPT: Dict[str, str] = {
    "بحریہ ٹاؤن": "Bahria Town", "بحریہ ٹائون": "Bahria Town", "ڈی ایچ اے": "DHA", "ڈیفنس": "DHA",
    "جوہر ٹاؤن": "Johar Town", "پارک ویو": "Park View", "اسلام آباد": "Islamabad", "راولپنڈی": "Rawalpindi",
    "لاہور": "Lahore", "کراچی": "Karachi", "گلبرگ": "Gulberg", "کلفٹن": "Clifton",
    "بیڈ رومز": "bedroom", "بیڈ روم": "bedroom", "بیڈروم": "bedroom", "خواب گاہ": "bedroom",
    "سوئمنگ پول": "swimming pool", "پول": "pool", "بیسمنٹ": "basement", "فرنشڈ": "furnished",
    "کروڑ": "crore", "لاکھ": "lakh", "مرلہ": "marla", "مرلے": "marla", "کنال": "kanal",
    "قیمت": "price", "کتنی": "", "کتنا": "", "کیا": "", "ہے": "", "ہیں": "", "میں": "in", "کی": "", "کا": "", "کے": "",
    "گھر": "house", "مکان": "house", "کوٹھی": "house", "فلیٹ": "flat", "اپارٹمنٹ": "apartment",
    "پلاٹ": "plot", "کمرشل": "commercial", "اقساط": "installment", "قسطوں": "installment",
    "سب سے سستا": "cheapest", "سب سے مہنگا": "most expensive", "اوسط": "average", "کتنے": "how many",
    "دکھائیں": "show", "بتائیں": "show", "بتاؤ": "show", "دکھاؤ": "show", "سے کم": "under", "سے زیادہ": "above",
    "نیچے": "under", "اوپر": "above", "والے": "", "والی": "", "والا": "", "وہ": "",
}
URDU_DIGIT_WORDS = {"صفر": "0", "ایک": "1", "دو": "2", "تین": "3", "چار": "4", "پانچ": "5", "چھ": "6",
                    "سات": "7", "آٹھ": "8", "نو": "9", "دس": "10", "ڈھائی": "2.5", "ساڑھے": "", "درجن": "12"}
URDU_ID_LETTERS = {"ایل اے ایچ": "LAH", "کے اے آر": "KAR", "آئی ایس ایل": "ISL", "آر اے ڈبلیو": "RAW"}

ROMAN_WORDS: Dict[str, str] = {
    "ghar": "house", "makaan": "house", "makan": "house", "kothi": "house", "ghr": "house",
    "qeemat": "price", "keemat": "price", "qimat": "price", "kimat": "price",
    "sasta": "cheapest", "sabse sasta": "cheapest", "sab se sasta": "cheapest", "sasti": "cheapest",
    "mehnga": "most expensive", "sabse mehnga": "most expensive", "sab se mehnga": "most expensive",
    "kitne": "how many", "kitni": "", "kitna": "", "kya": "", "hai": "", "hain": "", "ka": "", "ki": "", "ke": "", "mein": "in", "main": "in",
    "dikhao": "show", "dikhaye": "show", "dikhayen": "show", "batao": "show", "bataye": "show", "bataen": "show", "batayen": "show",
    "se kam": "under", "se zyada": "above", "se ziada": "above", "se upar": "above", "se neeche": "under", "tak": "",
    "wala": "", "wali": "", "wale": "", "koi": "", "kaun": "", "sa": "", "aur": "and",
    "qiston": "installment", "qist": "installment", "aqsat": "installment", "installments": "installment",
    "paisa": "", "rupay": "", "rupees": "",
}
ROMAN_NUMBERS = {"ek": "1", "do": "2", "teen": "3", "tin": "3", "char": "4", "chaar": "4", "paanch": "5", "panch": "5",
                 "chhe": "6", "chay": "6", "che": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10", "dhai": "2.5", "dedh": "1.5"}
ENGLISH_DIGIT_WORDS = {"zero": "0", "oh": "0", "sifar": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                       "six": "6", "seven": "7", "eight": "8", "nine": "9"}

ID_PREFIX = r"(?:lah|kar|isl|raw)"


def _sub_multiword(text: str, table: Dict[str, str], flags: int = 0) -> str:
    """Replace multi-word keys first (longest first), whole-token boundaries for Latin keys."""
    for key in sorted(table, key=len, reverse=True):
        if re.search(r"[\u0600-\u06FF]", key):
            text = text.replace(key, f" {table[key]} ")
        else:
            text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(key)}(?![A-Za-z0-9])", f" {table[key]} ", text, flags=re.I)
    return text


def spoken_ids_to_canonical(text: str) -> str:
    """'lah zero zero zero four' / 'L A H 0 0 0 4' / 'lah 0004' -> 'LAH-0004'."""
    t = text
    for k, v in URDU_ID_LETTERS.items():
        t = t.replace(k, f" {v} ")
    for w, d in URDU_DIGIT_WORDS.items():
        if d.isdigit() and len(d) == 1:
            t = re.sub(rf"(?<=\s){w}(?=\s|$)|^{w}(?=\s)", f" {d} ", t)
    tl = re.sub(r"\b([lLkKiIrR])\s+([aAsS])\s+([hHrRlLwW])\b", lambda m: (m.group(1) + m.group(2) + m.group(3)).lower(), t)
    tl = re.sub(rf"\b({ID_PREFIX})[\s\-]*((?:(?:\d|zero|oh|sifar|one|two|three|four|five|six|seven|eight|nine)[\s\-]*){{4,4}})",
                lambda m: f"{m.group(1).upper()}-" + "".join(ENGLISH_DIGIT_WORDS.get(x, x) for x in re.findall(r"\d|[a-z]+", m.group(2).lower())) + " ",
                tl, flags=re.I)
    return tl


def normalize_transcript(text: str) -> str:
    """Map an STT transcript (Urdu script / Roman Urdu / English / mixed) to a Latin query for Day-2 retrieval.

    Returns a whitespace-normalised string. Unknown words are left untouched. Deterministic, no network.
    """
    if not text:
        return ""
    t = text.translate(ARABIC_INDIC).replace("،", " ").replace("؟", " ").replace("۔", " ")
    t = spoken_ids_to_canonical(t)
    t = re.sub(rf"\b({'|'.join(ROMAN_NUMBERS)})\b(?=\s+(?:bed|bedroom|bedrooms|crore|lakh|lac|marla|kanal))",
               lambda m: ROMAN_NUMBERS[m.group(1).lower()], t, flags=re.I)
    # "3 کروڑ سے کم" / "3 crore se kam" / "3 crore tak" ->  "under 3 crore"
    unit = r"(crore|lakh|lac|lakhs|کروڑ|لاکھ)"
    under = r"(?:se\s+kam|سے\s+کم|نیچے|se\s+neeche|tak|below|under)"
    above = r"(?:se\s+(?:zyada|ziada|upar)|سے\s+(?:زیادہ|اوپر)|above|over)"
    unit_map = {"کروڑ": "crore", "لاکھ": "lakh", "lac": "lakh", "lakhs": "lakh"}
    t = re.sub(rf"(\d+(?:\.\d+)?)\s*{unit}\s*{under}", lambda m: f"under {m.group(1)} {unit_map.get(m.group(2).lower(), m.group(2).lower())}", t, flags=re.I)
    t = re.sub(rf"(\d+(?:\.\d+)?)\s*{unit}\s*{above}", lambda m: f"above {m.group(1)} {unit_map.get(m.group(2).lower(), m.group(2).lower())}", t, flags=re.I)
    t = _sub_multiword(t, URDU_SCRIPT)
    t = _sub_multiword(t, ROMAN_WORDS)
    for w, d in URDU_DIGIT_WORDS.items():
        if d:
            t = re.sub(rf"(?<![\u0600-\u06FF]){w}(?![\u0600-\u06FF])", f" {d} ", t)
    # number words directly before bedroom / unit words: "teen bedroom" -> "3 bedroom", "dhai crore" -> "2.5 crore"
    t = re.sub(rf"\b({'|'.join(ROMAN_NUMBERS)})\b(?=\s+(?:bed|bedroom|bedrooms|crore|lakh|lac|marla|kanal))",
               lambda m: ROMAN_NUMBERS[m.group(1).lower()], t, flags=re.I)
    t = re.sub(r"\b(\d+)[\s-]*(?:bed|beds|bedrooms?)\b", r"\1 bedroom", t, flags=re.I)
    t = re.sub(r"\bvillas?\b|\bbungalows?\b", "house", t, flags=re.I)
    t = re.sub(r"\bapartments?\b", "flat", t, flags=re.I) if False else t  # keep 'apartment' (parser maps it to Flat)
    t = re.sub(r"\s+", " ", t).strip()
    logger.debug("normalize: %r -> %r", text, t)
    return t


# --------------------------------------------------------------------------------------
# Speech-friendly rewriting for TTS
# --------------------------------------------------------------------------------------
def price_to_spoken(pkr: float) -> str:
    """325,500,000 -> '32 crore 55 lakh' (Pakistani convention; digits, English number words are read by TTS)."""
    pkr = int(round(pkr))
    crore, rem = divmod(pkr, 10_000_000)
    lakh, rem = divmod(rem, 100_000)
    thousand = rem // 1000
    parts: List[str] = []
    if crore:
        parts.append(f"{crore} crore")
    if lakh:
        parts.append(f"{lakh} lakh")
    if thousand and not crore:
        parts.append(f"{thousand} hazaar")
    return " ".join(parts) if parts else f"{pkr} rupay"


def spell_id(pid: str) -> str:
    """'LAH-0004' -> 'L A H, zero zero zero four' (comma gives TTS a pause between letters and digits)."""
    m = re.fullmatch(r"([A-Z]{3})-(\d{4})", pid)
    if not m:
        return pid
    digits = " ".join({"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine"}[c] for c in m.group(2))
    return f"{' '.join(m.group(1))}, {digits}"


# UNTESTED candidate respellings for English-first TTS reading Roman Urdu. Off by default.
PHONETIC_HINTS_CANDIDATES: Dict[str, str] = {"hain": "hein", "kijiye": "kijiyay", "nahi": "nahin"}


def prepare_for_tts(text: str, use_hints: bool = False) -> str:
    """Rewrite tokens that TTS engines commonly mispronounce. Idempotent for already-spoken text."""
    t = text
    t = re.sub(r"\b(?:LAH|KAR|ISL|RAW)-\d{4}\b", lambda m: spell_id(m.group(0)), t)
    t = re.sub(r"\bPKR\s*([\d,]+)", lambda m: price_to_spoken(int(m.group(1).replace(",", ""))), t)
    t = re.sub(r"\b(\d+)\.(\d{2})\s*crore\b", lambda m: price_to_spoken(float(f"{m.group(1)}.{m.group(2)}") * 10_000_000), t)
    t = re.sub(r"\b(\d+)\.(\d{2})\s*lac\b", lambda m: price_to_spoken(float(f"{m.group(1)}.{m.group(2)}") * 100_000), t)
    t = re.sub(r"\b(\d{1,2}),(\d{3})\s*(?:sqft|sq ft)\b", r"\1\2 square feet", t)
    t = re.sub(r"\bsqft\b", "square feet", t)
    t = re.sub(r"\b([A-Z])-(\d{1,2})\b", lambda m: f"{m.group(1)} {m.group(2)}", t)          # F-7 -> F 7
    t = re.sub(r"\bDHA\b", "D H A", t)
    t = re.sub(r"\bPKR\b", "rupay", t)
    if use_hints:
        for k, v in PHONETIC_HINTS_CANDIDATES.items():
            t = re.sub(rf"\b{k}\b", v, t)
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------------------
# Template renderer (zero-LLM path). Persona lines are placeholders until Day-1 docs exist.
# --------------------------------------------------------------------------------------
REFUSAL_TEXT = ("Maaf kijiye, main sirf property listings ke baare mein madad kar sakta hoon - "
                "Lahore, Karachi, Islamabad aur Rawalpindi ki sale listings.")
GREETING = "Assalam o Alaikum! Main property assistant hoon. Aap kis city aur budget mein property dekh rahe hain?"
GOODBYE = "Shukriya! Site visit ya booking ke liye kabhi bhi call kar sakte hain. Allah hafiz."
FILLER = "Ek second, main check karta hoon."
SILENCE_PROMPT = "Hello? Kya aap wahan hain? Aap apna budget ya city bata dein."
REPEAT_PROMPT = "Maaf kijiye, awaaz clear nahi aayi. Kya aap dobara bata sakte hain?"
CLARIFY = "Mujhe exact match nahi mila. Kya aap city, budget aur bedrooms dobara bata sakte hain?"
PASSAGE_MIN_SCORE = 0.45   # below this a semantic (TF-IDF) hit is too weak to read out as an answer
CACHED_PHRASES: Dict[str, str] = {"greeting": GREETING, "goodbye": GOODBYE, "filler": FILLER,
                                  "silence": SILENCE_PROMPT, "repeat": REPEAT_PROMPT, "refusal": REFUSAL_TEXT, "clarify": CLARIFY}


def _short(row: Dict[str, Any]) -> str:
    bed = f"{row['bedrooms']} bedroom " if row.get("bedrooms") is not None else ""
    return f"{bed}{row['property_type']} in {row['area']}, {row['city']}, {price_to_spoken(row['price_pkr'])}"


def render_reply(payload: Dict[str, Any], sources: List[str], get_property) -> str:
    """Render a Day-2 answer payload as short UrduLish text. ``get_property(pid)`` returns a row dict or None.

    Every number/ID in the output comes from the payload or a cited row (no free generation)."""
    k = payload.get("kind")
    if k == "refusal":
        return REFUSAL_TEXT
    if k == "not_found":
        return f"Mujhe {payload['id']} ID ki koi listing nahi mili. Kya aap ID dobara bata sakte hain?"
    if k == "not_recorded":
        return f"{payload['id']} ki listing mein {payload['field'].replace('_', ' ')} ki information available nahi hai."
    if k == "value":
        pid, f, v = payload["id"], payload["field"], payload["value"]
        if f == "price_pkr":
            return f"{pid} ki price {price_to_spoken(v)} hai."
        if f == "bedrooms":
            return f"{pid} mein {v} bedrooms hain."
        if f == "bathrooms":
            return f"{pid} mein {v} bathrooms hain."
        if f == "size_sqft":
            return f"{pid} ka size {v} square feet hai."
        if f == "property_type":
            return f"{pid} ek {v} hai."
        if f == "developer":
            return (f"{pid} ka developer ka naam listing mein clear nahi hai." if v == "Private / Unknown"
                    else f"{pid} ka developer {v} hai.")
        if f == "area":
            return f"{pid} {v} mein hai."
        row = get_property(pid)
        return (_short(row) + " hai.") if row else REFUSAL_TEXT
    if k == "count":
        return f"Aap ke criteria par {payload['value']} listings match karti hain."
    if k == "aggregate":
        op, v = payload["op"], payload["value"]
        if op == "top_developer":
            return f"Sab se zyada listings {v} ki hain, {payload['n']} listings."
        if op == "avg":
            return f"Average price {price_to_spoken(v)} hai, {payload['n']} listings ke hisaab se."
        if op == "median":
            return f"Median price {price_to_spoken(v)} hai, {payload['n']} listings ke hisaab se."
        row = get_property(payload.get("id", ""))
        word = "sasti" if op == "min" else "mehngi"
        return f"Sab se {word} listing {payload.get('id')} hai: {_short(row)}." if row else f"Sab se {word} price {price_to_spoken(v)} hai."
    if k == "none":
        return "Is criteria par koi listing nahi mili. Listing text mein is ka zikr nahi hai, is ka matlab ye nahi ke wo maujood nahi. Kya main criteria thoda change kar ke dekhun?"
    if k in ("ids", "passages"):
        ids = payload.get("ids", sources)
        if k == "passages" and (not payload.get("scores") or max(payload["scores"]) < PASSAGE_MIN_SCORE):
            return CLARIFY                     # weak semantic match: ask, do not read out an unrelated listing
        row = next((x for x in (get_property(i) for i in ids[:1]) if x), None)
        if not row:
            return "Is baare mein mujhe koi clear listing nahi mili."
        n = len(ids)
        head = ("Sab se qareeb listing ye hai: " if k == "passages" else
                (f"{n} listing mili hai: " if n == 1 else f"{n} listings mili hain. Ek listing ye hai: "))
        return f"{head}{spell_id(row['property_id'])}, {_short(row)}. Aur details chahiye?"
    return REFUSAL_TEXT
