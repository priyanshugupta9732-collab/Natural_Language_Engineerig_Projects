"""Problem 2 - dictionary-based regular-expression extraction of ingredients.

Lexicon  : surface forms taken from ingredient_mapping_listed_to_grouped.xlsx
           (listed names + split/cleaned grouped labels)
Pattern  : one big case-insensitive regex built from a trie, longest match wins
Output   : matches.tsv (one row per match) + stats printed to stdout
"""
import re, sys, time, csv
import pandas as pd

XLSX = "ingredient_mapping_listed_to_grouped.xlsx"
REVIEWS = "reviews.txt"

# ---------------------------------------------------------------- lexicon
def clean(s):
    s = str(s).lower().strip()
    return s

def build_lexicon(stoplist=frozenset(), drop_unmapped=True):
    m = pd.read_excel(XLSX, sheet_name="Mapping")
    g = pd.read_excel(XLSX, sheet_name="Grouped to listed")
    lex = {}  # surface form -> grouped label

    # (1) the 3,322 listed names -> their grouped label
    for name, label in zip(m.ingredient_as_listed, m.ingredient_grouped):
        n = clean(name)
        if not re.fullmatch(r"[a-z][a-z \-']*[a-z]", n):      # drop digits, brackets, '&', ...
            continue
        if label == "(unmapped)" and drop_unmapped:           # non-ingredients: 'up', 'or', 'can', 'skewer', ...
            continue
        lex[n] = label

    # (2) the grouped labels themselves, split into plain surface forms
    for label in g.ingredient_grouped:
        base = re.sub(r"\s*\(.*?\)", "", label)               # "beans (unspecified)" -> "beans"
        for part in re.split(r"/", base):                      # "anise/star anise" -> 2 forms
            part = clean(part)
            if part in ("other", "prepared") or len(part) < 3:
                continue
            lex.setdefault(part, label)
    # a few forms the label cleaning cannot produce
    lex.setdefault("buns", "rolls/buns"); lex.setdefault("rolls", "rolls/buns")
    lex.setdefault("jello", "gelatin/jello"); lex.setdefault("cool whip", "whipped cream/cool whip")

    for w in stoplist:
        lex.pop(w, None)
    return lex

# ---------------------------------------------------------------- regex
def variants(term):
    """singular + simple plural forms"""
    out = {term, term + "s", term + "es"}
    if term.endswith("y"):
        out.add(term[:-1] + "ies")
    if term.endswith("f"):
        out.add(term[:-1] + "ves")
    return out

def trie_regex(terms):
    """compile a set of strings into a compact regex alternation (trie) -> fast matching"""
    trie = {}
    for t in terms:
        node = trie
        for ch in t:
            node = node.setdefault(ch, {})
        node[""] = True

    def rec(node):
        if "" in node and len(node) == 1:
            return ""
        alts, optional = [], "" in node
        for ch in sorted(k for k in node if k != ""):
            sub = rec(node[ch])
            if ch == " ":
                ch = "[ -]"                                   # space and hyphen are interchangeable
            elif ch == "-":
                ch = "[ -]"
            else:
                ch = re.escape(ch)
            alts.append(ch + sub)
        body = alts[0] if len(alts) == 1 else "(?:" + "|".join(alts) + ")"
        return "(?:" + body + ")?" if optional else body
    return rec(trie)

def compile_pattern(lex):
    forms = set()
    surface_to_label = {}
    for term, label in lex.items():
        for v in variants(term):
            forms.add(v.replace("-", " "))                    # normalise hyphen -> space
            surface_to_label[v.replace("-", " ")] = label
    # longest alternatives must win -> the trie regex is greedy, so the longest path is taken
    rx = r"(?<![A-Za-z])(?:" + trie_regex(forms) + r")(?![A-Za-z])"
    return re.compile(rx, re.IGNORECASE), surface_to_label

# ---------------------------------------------------------------- run
def read_reviews():
    with open(REVIEWS, encoding="utf-8") as f:
        next(f)
        for i, line in enumerate(f):
            title, _, text = line.rstrip("\n").partition("\t")
            yield i, title, text

def run(lex, out_path):
    pat, s2l = compile_pattern(lex)
    n = hits = 0
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, delimiter="\t")
        w.writerow(["review_id", "start", "end", "surface", "grouped", "in_title"])
        for i, title, text in read_reviews():
            n += 1
            tl = title.lower()
            found = False
            for mt in pat.finditer(text):
                surf = mt.group(0).lower().replace("-", " ")
                lab = s2l.get(surf)
                if lab is None:
                    continue
                found = True
                w.writerow([i, mt.start(), mt.end(), surf, lab, int(surf in tl)])
            hits += found
    return n, hits, time.time() - t0

if __name__ == "__main__":
    lex = build_lexicon()
    print("lexicon size (surface forms):", len(lex))
    n, hits, dt = run(lex, "matches_A.tsv")
    print(f"reviews: {n}, with >=1 match: {hits} ({hits/n:.1%}), time {dt:.0f}s")
