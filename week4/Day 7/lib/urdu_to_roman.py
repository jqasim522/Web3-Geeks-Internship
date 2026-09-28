"""
urdu_to_roman.py — Urdu (Nastaliq) → Roman Urdu transliteration.
Phrase-level dictionary lookup (longest match first) + character fallback.
Zero external dependencies.
"""

# ---- Known phrases dictionary (longest multi-word entries first) ----
URDU_DICT = {
    # Multi-word phrases (longest first — MUST be checked before word-by-word)
    "ڈی ایچ اے": "DHA",
    "بہریہ ٹاؤن": "Bahria Town",
    "جوہر ٹاؤن": "Johar Town",
    "پارک ویو": "Park View",
    "ایف سیون": "F-7",
    "ایف ایٹ": "F-8",
    "ایف ٹین": "F-10",
    "ماڈل ٹاؤن": "Model Town",
    "بنڈ روڈ": "Bund Road",
    "نیو لاہور": "New Lahore",
    "فارم ہاؤس": "farm house",
    "بیڈ روم": "bedroom",
    "باتھ روم": "bathroom",
    "سوئمنگ پول": "swimming pool",
    "تہہ خانہ": "basement",
    "اسکوائر فٹ": "square feet",
    "اسکوائر یارڈ": "square yard",

    # Cities
    "لاہور": "Lahore", "کراچی": "Karachi", "اسلام آباد": "Islamabad",
    "راولپنڈی": "Rawalpindi", "فیصل آباد": "Faisalabad", "پشاور": "Peshawar",
    "کوئٹہ": "Quetta", "ملتان": "Multan", "حیدرآباد": "Hyderabad",

    # Areas / Developers
    "گلبرگ": "Gulberg", "کلفٹن": "Clifton", "گلشن": "Gulshan",

    # Property types
    "مکان": "house", "گھر": "house", "فلیٹ": "flat", "اپارٹمنٹ": "apartment",
    "پلاٹ": "plot", "دکان": "shop", "دفتر": "office",
    "پورشن": "portion", "کمرہ": "room",

    # Rooms / Features
    "بیڈروم": "bedroom", "باتھروم": "bathroom", "کچن": "kitchen",
    "لان": "lawn", "گیراج": "garage", "بے سمٹ": "basement",
    "لفٹ": "lift", "سولر": "solar", "فرنشڈ": "furnished",

    # Land measures
    "مرلہ": "marla", "کنال": "kanal", "ایکڑ": "acre", "گز": "gaz",

    # Money
    "کروڑ": "crore", "لاکھ": "lakh", "ہزار": "hazar", "روپے": "rupees",

    # Question words
    "کیا": "kya", "کہاں": "kahan", "کون": "kon", "کیسے": "kaise",
    "کتنا": "kitna", "کتنی": "kitni", "کونسا": "konsa",

    # Common verbs
    "چاہیے": "chahiye", "چاہیئے": "chahiye", "دکھائیں": "dikhaen",
    "بتائیں": "bataen", "ہے": "hai", "ہیں": "hain", "تھا": "tha",
    "تھی": "thi", "تھے": "the", "ہو": "ho", "ہوگا": "hoga",

    # Pronouns / connectors
    "میں": "mein", "ہم": "hum", "آپ": "aap", "وہ": "wo",
    "یہ": "yeh", "اور": "aur", "کے": "ke", "کی": "ki", "کا": "ka",
    "کو": "ko", "سے": "se", "پر": "par", "لیے": "liye",
    "تلاش": "talash", "دھونڈ": "dhoond", "چاہتا": "chahta",
    "چاہتی": "chahti", "چاہتے": "chahte",

    # Multi-word fragments (for when they appear standalone)
    "ڈی ایچ": "DH",
    "بیڈ": "bed",
    "روم": "room",
}

# Pre-sort multi-word keys by length (descending) for longest-match-first
_MULTIWORD_KEYS = sorted(
    [k for k in URDU_DICT if " " in k],
    key=len,
    reverse=True,
)

# ---- Character-level fallback mapping ----
CHAR_MAP = {
    "ا": "a", "آ": "aa", "ب": "b", "پ": "p", "ت": "t", "ٹ": "tt",
    "ث": "s", "ج": "j", "چ": "ch", "ح": "h", "خ": "kh",
    "د": "d", "ڈ": "dd", "ذ": "z", "ر": "r", "ڑ": "rr",
    "ز": "z", "ژ": "zh", "س": "s", "ش": "sh", "ص": "s", "ض": "z",
    "ط": "t", "ظ": "z", "ع": "a", "غ": "gh", "ف": "f", "ق": "q",
    "ک": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n", "ں": "n",
    "و": "o", "ہ": "h", "ھ": "h", "ء": "", "ی": "i", "ے": "e",
    "ۃ": "h", "ؤ": "o", "ئ": "i",
    "َ": "a", "ِ": "i", "ُ": "u", "ْ": "", "ّ": "", "ٰ": "a",
    "۔": ".", "،": ",", "؟": "?", "!": "!",
}


def _apply_phrases(text: str) -> str:
    """Replace longest multi-word phrases first (before word-by-word split)."""
    result = text
    for phrase in _MULTIWORD_KEYS:
        replacement = URDU_DICT[phrase]
        result = result.replace(phrase, f"__{replacement}__")
    return result


def urdu_to_roman(text: str) -> str:
    """Transliterate Urdu script to Roman Urdu."""
    if not text:
        return text
    # Check if any Urdu characters exist
    if not any('\u0600' <= c <= '\u06FF' for c in text):
        return text  # Already Roman or English

    # 1. First pass: replace multi-word phrases (longest-first) with placeholders
    text_with_phrases = _apply_phrases(text)

    # 2. Second pass: word-by-word transliteration
    words = text_with_phrases.split()
    result = []
    for word in words:
        # Strip punctuation
        punc = ""
        while word and word[-1] in "۔،؟!.":
            punc = word[-1] + punc
            word = word[:-1]

        # Placeholder from phrase pass? Skip dictionary lookup.
        if word.startswith("__") and word.endswith("__"):
            roman = word[2:-2]
        else:
            # Strip leading punctuation from placeholder cases (edge)
            roman = URDU_DICT.get(word)
            if not roman:
                roman = "".join(CHAR_MAP.get(c, c) for c in word)

        result.append(roman + punc)

    return " ".join(result)


def is_urdu(text: str) -> bool:
    """Check if text contains Urdu script characters."""
    return any('\u0600' <= c <= '\u06FF' for c in text)


# Quick test
if __name__ == "__main__":
    samples = [
        "لاہور میں",
        "لاہور میں تین بیڈ روم مکان چاہیے",
        "ڈی ایچ اے لاہور",
        "تین کروڑ پچاس لاکھ",
        "ایک کنال پلاٹ",
        "بیڈ روم",
        "ڈی ایچ اے",
    ]
    for s in samples:
        print(f"  {s}  →  {urdu_to_roman(s)}")