import pandas as pd

N_REVIEWS = 100000
A = pd.read_csv("matches_A.tsv", sep="\t")

# location string: r<review_id>:<start>-<end>
A["loc"] = "r" + A.review_id.astype(str) + ":" + A.start.astype(str) + "-" + A.end.astype(str)

# table 1: one row per grouped ingredient
agg = (A.groupby("grouped")
         .agg(mentions=("surface", "size"),
              reviews=("review_id", "nunique"))
         .sort_values("mentions", ascending=False))
agg["pct_of_reviews"] = (agg.reviews / N_REVIEWS * 100).round(2)

top_forms = (A.groupby(["grouped", "surface"]).size().reset_index(name="n")
               .sort_values(["grouped", "n"], ascending=[True, False])
               .groupby("grouped")
               .apply(lambda d: "; ".join(f"{s} ({n})" for s, n in zip(d.surface[:5], d.n[:5]))))
agg["top_surface_forms"] = top_forms
agg["example_locations"] = A.groupby("grouped")["loc"].apply(lambda s: ", ".join(s.iloc[:3]))

agg.to_csv("ingredient_table.csv")

# table 2: one row per surface form
sf = (A.groupby(["surface", "grouped"])
        .agg(mentions=("start", "size"), reviews=("review_id", "nunique"))
        .reset_index().sort_values("mentions", ascending=False))
sf.to_csv("surface_forms.csv", index=False)

print(agg.head(15))