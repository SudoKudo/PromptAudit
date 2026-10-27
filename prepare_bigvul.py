"""
**prepare_bigvul.py** prepares BigVul for PromptAudit using the same protocol as CVEfixes.

It extracts vulnerable and safe functions, cleans and deduplicates code, filters invalid samples, and selects CVE subsets stratified by disclosure year.

**Run from the PromptAudit project root:**
```bash
python prepare_bigvul.py
python prepare_bigvul.py --csv MSR_data_cleaned.csv
python prepare_bigvul.py --cves 50 100 500 1000
```

**Outputs** in `data/bigvul/` include paired code files, CSV datasets, a cleaning report, and a config snippet.

Disclosure years are recovered from `bigvul_cve_meta.csv` or the official CVE List, with results cached for future runs.

"""

import argparse, hashlib, json, random, re, shutil, sys, textwrap, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

HF_REPO = "bstee615/bigvul"
CVELIST_URL = "https://raw.githubusercontent.com/CVEProject/cvelistV5/main/cves/{y}/{b}xxx/{c}.json"
META_URL = "https://raw.githubusercontent.com/kchabra/Big-Vul/master/all_c_cpp_release2.0.csv"
COLUMN_ALIASES = {
    "func_before": ["func_before"], "func_after": ["func_after"], "vul": ["vul", "target"],
    "cve_id": ["CVE ID", "cve_id"], "cwe_id": ["CWE ID", "cwe_id"], "project": ["project"],
    "commit_id": ["commit_id"], "lang": ["lang"], "publish_date": ["Publish Date", "publish_date"],
    "cvss_score": ["Score", "score"],
}


# ----------------------------------------------------------------------------- loading
def load_raw(csv_path=None):
    if csv_path:
        print(f"[load] Reading {csv_path}")
        df = pd.read_csv(csv_path, low_memory=False)
    else:
        print(f"[load] Downloading {HF_REPO} from HuggingFace...")
        from datasets import load_dataset
        ds = load_dataset(HF_REPO)
        df = pd.concat([ds[s].to_pandas() for s in ds], ignore_index=True)
    print(f"[load] {len(df):,} raw rows")
    out = pd.DataFrame()
    for canon, opts in COLUMN_ALIASES.items():
        col = next((c for c in opts if c in df.columns), None)
        if col is None and canon in ("func_before", "func_after", "vul", "cve_id"):
            sys.exit(f"Required column '{canon}' missing. Columns: {list(df.columns)}")
        out[canon] = df[col] if col else None
    return out


def load_meta(path_hint):
    here = Path(__file__).resolve().parent
    for p in [path_hint, here / "bigvul_cve_meta.csv", Path("data/bigvul_cve_meta.csv")]:
        if p and Path(p).exists():
            print(f"[meta] Using {p}")
            return pd.read_csv(p), Path(p)
    print(f"[meta] bigvul_cve_meta.csv not found; building it from {META_URL}")
    m = pd.read_csv(META_URL, low_memory=False, usecols=["cve_id", "publish_date", "score"])
    m = m.dropna(subset=["cve_id"]).drop_duplicates("cve_id")
    m["year"] = pd.to_datetime(m.publish_date, errors="coerce").dt.year
    m["year_source"] = "bigvul"
    m.to_csv(here / "bigvul_cve_meta.csv", index=False)
    return m, here / "bigvul_cve_meta.csv"


def first_cve(s):
    hit = re.search(r"CVE-\d{4}-\d{4,}", str(s))
    return hit.group(0) if hit else None


def cvelist_date(cve):
    y, n = cve.split("-")[1], int(cve.split("-")[2])
    try:
        url = CVELIST_URL.format(y=y, b=n // 1000, c=cve)
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.load(r)["cveMetadata"].get("datePublished")
    except Exception:
        return None


def fill_missing_years(cves, meta, meta_path):
    """Look up publish dates for CVEs absent from the meta table; cache the results."""
    known = set(meta.dropna(subset=["year"]).cve_id)
    todo = sorted({c for c in cves if c and c not in known})
    if not todo:
        return meta
    print(f"[meta] {len(todo)} CVEs have no year in bigvul_cve_meta.csv; fetching from the CVE List...")
    with ThreadPoolExecutor(8) as ex:
        dates = list(ex.map(cvelist_date, todo))
    new = pd.DataFrame({"cve_id": todo, "publish_date": [d[:10] if d else None for d in dates]})
    new["year"] = pd.to_datetime(new.publish_date, errors="coerce").dt.year
    new["year_source"] = "cvelist"
    found = new.year.notna().sum()
    print(f"[meta] found {found}/{len(todo)}; caching to {meta_path}")
    if "year_source" not in meta:
        meta["year_source"] = "bigvul"
    meta = pd.concat([meta[~meta.cve_id.isin(new[new.year.notna()].cve_id)], new[new.year.notna()]],
                     ignore_index=True)
    meta.to_csv(meta_path, index=False)
    return meta


# ----------------------------------------------------------------------------- C text utils
def strip_comments(code):
    """Remove // and /* */ comments, respecting string and char literals."""
    out, i, n = [], 0, len(code)
    while i < n:
        c, nxt = code[i], code[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = code.find("\n", i); i = n if j == -1 else j
        elif c == "/" and nxt == "*":
            j = code.find("*/", i + 2)
            block = code[i:] if j == -1 else code[i:j + 2]
            out.append("\n" * block.count("\n") or " ")
            i = n if j == -1 else j + 2
        elif c in "\"'":
            j = i + 1
            while j < n and code[j] != c:
                j += 2 if code[j] == "\\" else 1
            out.append(code[i:j + 1]); i = j + 1
        else:
            out.append(c); i += 1
    return "".join(out)


def standardize(code):
    """Unify line endings, tabs -> 4 spaces, remove common indent, trailing spaces, blank runs."""
    code = code.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)
    code = textwrap.dedent("\n".join(ln.rstrip() for ln in code.split("\n")))
    return re.sub(r"\n{3,}", "\n\n", code).strip() + "\n"


def squash(code):
    return re.sub(r"\s+", "", code)


def looks_complete(code):
    body = re.sub(r'"(\\.|[^"\\])*"|\'(\\.|[^\'\\])*\'', '""', strip_comments(code))
    o, c = body.count("{"), body.count("}")
    return o > 0 and o == c and body.rstrip().endswith("}")


def n_lines(code):
    return sum(1 for ln in code.split("\n") if ln.strip())


def tokens(code):
    return re.findall(r"\w+|[^\w\s]", strip_comments(code))


def sha(s):
    return hashlib.sha1(s.encode("utf-8", "ignore")).hexdigest()


# ----------------------------------------------------------------------------- near-duplicates
class NearDup:
    """Greedy near-duplicate filter: MinHash-LSH for candidates, token SequenceMatcher to confirm."""
    P = (1 << 61) - 1

    def __init__(self, threshold, n_hash=64, bands=16, seed=0):
        rng = np.random.default_rng(seed)
        self.a = rng.integers(1, self.P, n_hash, dtype=np.uint64)
        self.b = rng.integers(0, self.P, n_hash, dtype=np.uint64)
        self.thr, self.bands, self.rows = threshold, bands, n_hash // bands
        self.buckets = defaultdict(list)
        self.kept = []

    def _sig(self, toks):
        sh = {zlib.crc32(" ".join(toks[i:i + 3]).encode()) for i in range(max(1, len(toks) - 2))}
        x = np.fromiter(sh, dtype=np.uint64)
        return ((np.outer(x, self.a) + self.b) % self.P).min(axis=0)

    def is_dup_then_add(self, toks):
        sig = self._sig(toks)
        keys = [(i, sig[i * self.rows:(i + 1) * self.rows].tobytes()) for i in range(self.bands)]
        seen = set()
        for k in keys:
            for j in self.buckets.get(k, ()):
                if j in seen:
                    continue
                seen.add(j)
                other = self.kept[j]
                if min(len(toks), len(other)) / max(len(toks), len(other)) < 0.9:
                    continue
                sm = SequenceMatcher(None, toks, other, autojunk=False)
                if sm.quick_ratio() >= self.thr and sm.ratio() >= self.thr:
                    return True
        idx = len(self.kept)
        self.kept.append(toks)
        for k in keys:
            self.buckets[k].append(idx)
        return False


# ----------------------------------------------------------------------------- scrub
def scrub(df, meta, meta_path, a):
    R = {"raw_rows": len(df)}
    step = lambda name, d: R.__setitem__(name, len(d)) or d

    df = step("vul_1_rows", df[pd.to_numeric(df.vul, errors="coerce") == 1].copy())
    if df.lang.notna().any():
        df["lang"] = df.lang.astype(str).str.strip().replace({"CPP": "C++", "cpp": "C++"})
        df = step("c_cpp_only", df[df.lang.isin(["C", "C++"])])
    df["cve_id"] = df.cve_id.map(first_cve)
    df = step("has_cve_id", df.dropna(subset=["cve_id"]))
    df = df.dropna(subset=["func_before", "func_after"])
    df = step("non_empty", df[(df.func_before.str.strip() != "") & (df.func_after.str.strip() != "")])

    prep = (lambda s: standardize(strip_comments(s))) if a.strip_comments else standardize
    df["code_vuln"] = df.func_before.astype(str).map(prep)
    df["code_safe"] = df.func_after.astype(str).map(prep)

    # compare with comments removed, so comment-only "fixes" are dropped either way
    df = step("has_code_change", df[df.code_vuln.map(lambda s: squash(strip_comments(s)))
                                    != df.code_safe.map(lambda s: squash(strip_comments(s)))])
    df = step("not_truncated", df[df.code_vuln.map(looks_complete) & df.code_safe.map(looks_complete)])
    df = step(f"min_{a.min_lines}_lines",
              df[(df.code_vuln.map(n_lines) >= a.min_lines) & (df.code_safe.map(n_lines) >= a.min_lines)])
    if a.max_chars:
        df = step(f"max_{a.max_chars}_chars",
                  df[(df.code_vuln.str.len() <= a.max_chars) & (df.code_safe.str.len() <= a.max_chars)])

    df["hv"] = df.code_vuln.map(lambda s: sha(squash(s)))
    df["hs"] = df.code_safe.map(lambda s: sha(squash(s)))
    df = df.drop_duplicates("hv").drop_duplicates("hs")
    df = step("exact_dedup", df)
    conflict = set(df.hv) & set(df.hs)
    df = step("no_label_conflicts", df[~df.hv.isin(conflict) & ~df.hs.isin(conflict)])

    print(f"[scrub] near-duplicate check (> {a.near_dup:.0%}) on {len(df):,} pairs...")
    df = df.sample(frac=1, random_state=a.seed).reset_index(drop=True)
    nd_v, nd_s, keep = NearDup(a.near_dup), NearDup(a.near_dup), []
    for i, r in enumerate(df.itertuples()):
        tv, ts = tokens(r.code_vuln), tokens(r.code_safe)
        dup_v = nd_v.is_dup_then_add(tv)
        dup_s = nd_s.is_dup_then_add(ts) if not dup_v else True
        keep.append(not (dup_v or dup_s))
        if (i + 1) % 2000 == 0:
            print(f"        {i + 1:,}/{len(df):,}")
    df = step("near_dedup", df[keep])

    if not df.publish_date.notna().any():
        meta = fill_missing_years(df.cve_id.unique(), meta, meta_path)
    if "year_source" in meta:
        R["cves_dated_from_cvelist"] = int(meta[meta.year_source.eq("cvelist") & meta.cve_id.isin(set(df.cve_id))].shape[0])
    meta = meta.dropna(subset=["cve_id"]).drop_duplicates("cve_id").set_index("cve_id")
    if df.publish_date.notna().any():
        df["year"] = pd.to_datetime(df.publish_date, errors="coerce").dt.year
    else:
        df["year"] = df.cve_id.map(meta["year"])
    if df.cvss_score.isna().all() and "score" in meta:
        df["cvss_score"] = df.cve_id.map(meta["score"])
    df = step("has_disclosure_year", df[df.year.notna()])
    df["year"] = df.year.astype(int)

    R["clean_pairs"] = len(df)
    R["clean_cves"] = int(df.cve_id.nunique())
    R["clean_year_distribution"] = {int(k): int(v) for k, v in
                                    df.drop_duplicates("cve_id").year.value_counts().sort_index().items()}
    return df.reset_index(drop=True), R


# ----------------------------------------------------------------------------- selection
def stratified_cves(pairs, n, seed):
    """Pick n CVEs, preserving the disclosure-year distribution (largest-remainder allocation)."""
    by_year = pairs.drop_duplicates("cve_id").groupby("year").cve_id.apply(sorted).to_dict()
    total = sum(map(len, by_year.values()))
    if n >= total:
        return [c for y in sorted(by_year) for c in by_year[y]]
    quota = {y: n * len(v) / total for y, v in by_year.items()}
    alloc = {y: int(q) for y, q in quota.items()}
    for y in sorted(quota, key=lambda y: quota[y] - alloc[y], reverse=True)[: n - sum(alloc.values())]:
        alloc[y] += 1
    rng, picked = random.Random(seed), []
    for y in sorted(by_year):
        pool = by_year[y][:]
        rng.shuffle(pool)
        picked += pool[: alloc[y]]
    return picked


COLS = ["id", "language", "code", "label", "cve_id", "year", "cwe_id", "cvss_score", "project",
        "pair_id", "commit_id"]
EXT = {"C": "c", "C++": "cpp"}
C_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "defined"}


def build_rows(pairs, cves, seed):
    sub = pairs[pairs.cve_id.isin(set(cves))].sample(frac=1, random_state=seed)
    rows = []
    for pid, r in enumerate(sub.itertuples(), 1):
        base = dict(cve_id=r.cve_id, year=r.year, cwe_id=r.cwe_id, cvss_score=r.cvss_score,
                    project=r.project, language=r.lang if r.lang in EXT else "C",
                    pair_id=pid, commit_id=r.commit_id)
        rows.append({**base, "code": r.code_vuln, "label": "VULNERABLE"})
        rows.append({**base, "code": r.code_safe, "label": "SAFE"})
    out = pd.DataFrame(rows)
    out["id"] = range(1, len(out) + 1)
    return out[COLS]


def function_name(code):
    """Name of the function defined in a snippet (identifier before the first '(' of the header)."""
    header = strip_comments(code).split("{", 1)[0]
    names = [n for n in re.findall(r"([A-Za-z_]\w*)\s*\(", header) if n not in C_KEYWORDS]
    return names[0] if names else "function"


def write_cve_folders(rows, root):
    """Write the cve_code_<N> layout: one folder per CVE, NN_before/NN_after files + README.txt."""
    if root.exists():
        shutil.rmtree(root)
    for cve, g in rows.groupby("cve_id", sort=True):
        d = root / cve
        d.mkdir(parents=True)
        files, commits = [], []
        for k, (pid, pair) in enumerate(g.groupby("pair_id", sort=True), 1):
            v = pair[pair.label == "VULNERABLE"].iloc[0]
            sfe = pair[pair.label == "SAFE"].iloc[0]
            fname = f"{function_name(v.code)}.{EXT.get(v.language, 'c')}"
            (d / f"{k:02d}_before_{fname}.txt").write_text(v.code, encoding="utf-8")
            (d / f"{k:02d}_after_{fname}.txt").write_text(sfe.code, encoding="utf-8")
            files.append(fname)
            if isinstance(v.commit_id, str) and v.commit_id not in commits:
                commits.append(v.commit_id)
        readme = (f"CVE: {cve}\nTotal file changes: {len(files)}\n"
                  f"Commit hash(es): {', '.join(commits)}\n\nFiles changed:\n"
                  + "".join(f"  {i}. {f}\n" for i, f in enumerate(files, 1)))
        (d / "README.txt").write_text(readme, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", help="Local MSR_data_cleaned.csv instead of HuggingFace")
    ap.add_argument("--meta", help="Path to bigvul_cve_meta.csv (CVE -> year, CVSS)")
    ap.add_argument("--out", default="data/bigvul")
    ap.add_argument("--cves", nargs="*", type=int, default=[50, 100, 500, 1000],
                    help="Subset sizes in CVEs (paper used 1000)")
    ap.add_argument("--min-lines", type=int, default=10, help="Paper: 10")
    ap.add_argument("--near-dup", type=float, default=0.98, help="Paper: 0.98")
    ap.add_argument("--max-chars", type=int, default=0,
                    help="Optional cap on function length (0 = off, as in the paper)")
    ap.add_argument("--strip-comments", action="store_true",
                    help="Remove comments from the code (not in the paper; reduces label leakage)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--no-folders", action="store_true")
    a = ap.parse_args()

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    meta, meta_path = load_meta(a.meta)
    pairs, report = scrub(load_raw(a.csv), meta, meta_path, a)
    for k, v in report.items():
        if not isinstance(v, dict):
            print(f"[scrub] {k:<26} {v:,}")
    if pairs.empty:
        sys.exit("No pairs survived scrubbing.")

    snippet, report["subsets"] = [], {}
    for n in sorted(a.cves):
        rows = build_rows(pairs, stratified_cves(pairs, n, a.seed), a.seed)
        name = f"bigvul_{n}"
        rows.to_csv(out / f"{name}.csv", index=False)
        if not a.no_folders:
            write_cve_folders(rows, out / name)
        report["subsets"][name] = {"cves": int(rows.cve_id.nunique()), "samples": len(rows)}
        target = f"{name}.csv" if a.no_folders else f"{name}/"
        snippet.append(f"  - name: {name}\n    source: local\n    path: {out.as_posix()}/{target}\n")
        print(f"[export] {name}: {rows.cve_id.nunique()} CVEs -> {len(rows)} samples")

    report["settings"] = {k: v for k, v in vars(a).items()}
    report["settings"]["source"] = a.csv or f"huggingface:{HF_REPO}"
    (out / "scrub_report.json").write_text(json.dumps(report, indent=2))
    (out / "config_snippet.yaml").write_text("# paste under `datasets:` in config.yaml\n" + "".join(snippet))
    print(f"[done] {out.resolve()}")


if __name__ == "__main__":
    main()
