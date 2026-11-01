"""Problem 3 - LLM-based ingredient extraction, two prompt variants.

  python llm_extract.py run --variant plain   --n 200      # no contextual information
  python llm_extract.py run --variant context --n 200      # + Problem-1 mapping information
  python llm_extract.py compare                            # compare both variants and the regex result

Needs:  pip install anthropic pandas openpyxl   and   export ANTHROPIC_API_KEY=...
"""
import argparse, json, random, re, time
import pandas as pd

XLSX = "ingredient_mapping_listed_to_grouped.xlsx"
REVIEWS = "reviews.txt"
MODEL = "claude-sonnet-5-5"          # change if your account/course uses another model

# ------------------------------------------------------------------ prompts
PROMPT_PLAIN = """You are an information extraction system for recipe reviews.
Task: find every phrase in the review that names a food ingredient (including drinks, spices, sauces and brands used as ingredients).
Rules:
- Return the phrase as it appears in the review, without quantities ("2 cups of flour" -> "flour").
- Do NOT return the name of the dish that is being reviewed, cooking equipment or generic words.
- Return each distinct ingredient once.
Answer with JSON only, no explanation, in this form: {"ingredients": ["...", "..."]}"""

def build_context_prompt(full_mapping=False):
    m = pd.read_excel(XLSX, sheet_name="Mapping")
    g = pd.read_excel(XLSX, sheet_name="Grouped to listed")
    labels = sorted(g.ingredient_grouped)
    # curated from the 'Unmapped' sheet: only real NON-ingredients (the sheet also contains real ingredients such as
    # achiote or bouquet garni, so it must not be passed on as a whole)
    not_ing = ["as desired", "optional", "garnish", "toothpick", "skewer", "canning jar", "cedar plank",
               "freshly", "boned", "can", "regular", "up", "or", "each", "roll", "mix", "sprinkle", "topping"]
    p = """You are an information extraction system for recipe reviews.
Task: find every phrase in the review that names a food ingredient and map it to ONE label from the fixed label list below.
Rules:
- "mention" is the phrase as it appears in the review, without quantities.
- "label" must be copied exactly from the label list. If no label fits, use "OTHER".
- Do NOT return the name of the dish that is being reviewed, cooking equipment, or generic words.
- Words like the following are NOT ingredients: """ + ", ".join(not_ing) + """.
- Beware of compounds: "butter bean" is not butter, "sugar cookie" is a dish, "egg roll wrap" is not egg.
- Return each distinct ingredient once.

LABEL LIST (""" + str(len(labels)) + """ labels):
""" + "; ".join(labels)
    if full_mapping:   # optional: all listed names with their grouped label (long prompt!)
        pairs = m[m.ingredient_grouped != "(unmapped)"]
        p += "\n\nEXAMPLES listed name = label:\n" + "\n".join(
            f"{a} = {b}" for a, b in zip(pairs.ingredient_as_listed, pairs.ingredient_grouped))
    p += '\n\nAnswer with JSON only, no explanation: {"ingredients": [{"mention": "...", "label": "..."}]}'
    return p

# ------------------------------------------------------------------ helpers
def read_reviews():
    with open(REVIEWS, encoding="utf-8") as f:
        next(f)
        for i, line in enumerate(f):
            title, _, text = line.rstrip("\n").partition("\t")
            yield i, title, text

def parse_json(txt):
    a, b = txt.find("{"), txt.rfind("}")
    try:
        return json.loads(txt[a:b + 1])["ingredients"]
    except Exception:
        return None            # parse failure is counted and reported

def sample_ids(n, seed, max_len):
    rows = [(i, t, x) for i, t, x in read_reviews() if 60 <= len(x) <= max_len]
    random.Random(seed).shuffle(rows)
    return sorted(rows[:n])

# ------------------------------------------------------------------ run
def run(args):
    import anthropic
    client = anthropic.Anthropic()
    system = PROMPT_PLAIN if args.variant == "plain" else build_context_prompt(args.full_mapping)
    system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    rows = sample_ids(args.n, args.seed, args.max_len)
    out_path = f"llm_{args.variant}.jsonl"
    fails = 0
    with open(out_path, "w", encoding="utf-8") as fo:
        for k, (i, title, text) in enumerate(rows, 1):
            user = f"Recipe title: {title}\nReview: {text}" if args.with_title else f"Review: {text}"
            for attempt in range(3):
                try:
                    r = client.messages.create(model=MODEL, max_tokens=500, temperature=0,
                                               system=system_blocks,
                                               messages=[{"role": "user", "content": user}])
                    raw = r.content[0].text
                    break
                except Exception as e:
                    raw = f"ERROR {e}"; time.sleep(2 * (attempt + 1))
            parsed = parse_json(raw)
            fails += parsed is None
            fo.write(json.dumps({"review_id": i, "title": title, "text": text, "raw": raw, "parsed": parsed},
                                ensure_ascii=False) + "\n")
            if k % 20 == 0:
                print(k, "reviews done")
    print(f"saved {out_path}; JSON parse failures: {fails}")

# ------------------------------------------------------------------ compare
def mentions(rec, variant):
    if not rec["parsed"]:
        return []
    out = []
    for x in rec["parsed"]:
        out.append((x if variant == "plain" else x.get("mention", "")).lower().strip())
    return out

def load(variant):
    return {json.loads(l)["review_id"]: json.loads(l) for l in open(f"llm_{variant}.jsonl", encoding="utf-8")}

def compare(args):
    P, C = load("plain"), load("context")
    ids = sorted(set(P) & set(C))
    A = pd.read_csv("matches_A.tsv", sep="\t")
    A = A[A.review_id.isin(ids)]
    regex = A.groupby("review_id").surface.apply(lambda s: set(s))
    rows = []
    for i in ids:
        p, c = set(mentions(P[i], "plain")), set(mentions(C[i], "context"))
        r = regex.get(i, set())
        rows.append({"review_id": i, "n_plain": len(p), "n_context": len(c), "n_regex": len(r),
                     "plain_only": "; ".join(sorted(p - c)), "context_only": "; ".join(sorted(c - p)),
                     "regex_not_in_plain": "; ".join(sorted(x for x in r if not any(x in m for m in p))),
                     "plain_not_in_regex": "; ".join(sorted(x for x in p if not any(x in m for m in r))),
                     "text": P[i]["text"]})
    df = pd.DataFrame(rows)
    df.to_csv("llm_comparison.csv", index=False)
    print(df[["n_plain", "n_context", "n_regex"]].describe().loc[["mean", "sum"]])
    # annotation sheets: fill the column 'correct' (1/0) yourself, then compute precision
    for v, D in (("plain", P), ("context", C)):
        ann = [{"review_id": i, "mention": m, "correct": ""} for i in ids for m in mentions(D[i], v)]
        pd.DataFrame(ann).to_csv(f"llm_annotation_{v}.csv", index=False)
    lab = [x.get("label") for i in ids if C[i]["parsed"] for x in C[i]["parsed"]]
    print("context variant: share of mentions labelled OTHER:", round(lab.count("OTHER") / max(1, len(lab)), 3))
    g = set(pd.read_excel(XLSX, sheet_name="Grouped to listed").ingredient_grouped)
    print("context variant: labels not in the list:", sum(1 for l in lab if l not in g and l != "OTHER"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--variant", choices=["plain", "context"], required=True)
    r.add_argument("--n", type=int, default=200)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--max_len", type=int, default=600)
    r.add_argument("--with_title", action="store_true")
    r.add_argument("--full_mapping", action="store_true")
    sub.add_parser("compare")
    a = ap.parse_args()
    run(a) if a.cmd == "run" else compare(a)