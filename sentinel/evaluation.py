"""How good is Sentinel on REAL data? (Objective 6 of the Final Project: Testing & Evaluation)

- Phishing: 200 real phishing emails (Phishing Pot) + 500 real normal emails (Enron).
  Rules alone on all 700 emails, then rules vs LLM agent vs LLM agent + guardrail on a sample (the free LLM is slow).
- Arabic sentiment: 4,272 real reviews whose label comes from the star rating.
"""
import time

import pandas as pd

from . import config
from .llm import get_llm
from .phishing_agent import analyze_email
from .voc_agent import guess_sentiment, load_lexicon, load_reviews

PHISHING_DIR = config.ROOT / "datasets" / "phishing_pot"
HAM_FILE = config.ROOT / "datasets" / "enron_ham.csv"


def real_emails(max_emails=None, sample=False):
    """[(name, truth, raw email)] for the real phishing and the real normal emails."""
    phishing = sorted(PHISHING_DIR.glob("*.eml"))
    ham = pd.read_csv(HAM_FILE)
    if sample:   # the same random sample every time
        phishing = pd.Series(phishing).sample(min(max_emails, len(phishing)), random_state=7).tolist()
        ham = ham.sample(min(max_emails, len(ham)), random_state=7)
    else:
        phishing, ham = phishing[:max_emails], ham.head(max_emails)
    emails = [(p.name, "phishing", p.read_bytes()) for p in phishing]
    emails += [(r.subject[:60], "normal", f"From: employee@enron.com\nSubject: {r.subject}\n\n{r.message}")
               for r in ham.itertuples()]
    return emails


def metrics_of(table, verdict_column="verdict"):
    """Detection rate, false alarms, precision, accuracy. Flagged = phishing or suspicious."""
    flagged = table[verdict_column].isin(["phishing", "suspicious"])
    phishing, normal = table["truth"] == "phishing", table["truth"] == "normal"
    caught, false_alarms = (flagged & phishing).sum(), (flagged & normal).sum()
    return {
        "phishing_emails": int(phishing.sum()),
        "normal_emails": int(normal.sum()),
        "detection_rate": caught / max(phishing.sum(), 1),             # recall: attacks we caught
        "false_alarm_rate": false_alarms / max(normal.sum(), 1),       # normal emails wrongly flagged
        "precision": caught / max(caught + false_alarms, 1),           # of everything flagged, how much was really phishing
        "accuracy": ((flagged & phishing).sum() + (~flagged & normal).sum()) / len(table),
    }


def evaluate_phishing(max_emails=None):
    """Run the Phishing agent with the rules only (rules + ML, no LLM) on real emails and compare with the truth."""
    rows = []
    start = time.time()
    for name, truth, raw in real_emails(max_emails):
        result = analyze_email(raw, use_llm=False, remember=False)
        rows.append({"email": name, "truth": truth, "verdict": result["verdict"], "score": result["score"]})
    table = pd.DataFrame(rows)
    table["flagged"] = table["verdict"].isin(["phishing", "suspicious"])
    phishing, normal = table[table["truth"] == "phishing"], table[table["truth"] == "normal"]
    caught = phishing["flagged"].sum()
    false_alarms = normal["flagged"].sum()

    metrics = {
        "phishing_emails": len(phishing),
        "normal_emails": len(normal),
        "detection_rate": caught / len(phishing),                     # recall: attacks we caught
        "false_alarm_rate": false_alarms / len(normal),               # normal emails wrongly flagged
        "precision": caught / max(caught + false_alarms, 1),          # of everything flagged, how much was really phishing
        "accuracy": ((phishing["flagged"]).sum() + (~normal["flagged"]).sum()) / len(table),
        "ms_per_email": (time.time() - start) / len(table) * 1000,
    }
    return metrics, table


def compare_rules_and_llm(emails_each=10, llm=None, pause=4):
    """The key experiment: the same real emails, three ways.
    rules = the rule checks + ML only | LLM = the LLM agent's own verdict | LLM + guardrail = Sentinel's final verdict.
    pause = seconds between emails, to stay under the free LLM's requests-per-minute limit.
    """
    llm = llm or get_llm()
    if llm is None:
        return None, None
    rows = []
    for name, truth, raw in real_emails(emails_each, sample=True):
        start = time.time()
        analyze_email(raw, use_llm=False, remember=False)            # rules + ML alone: timed on its own
        rules_seconds = time.time() - start
        start = time.time()
        result = analyze_email(raw, llm=llm, remember=False)
        rows.append({"email": name, "truth": truth, "rules": result["extra"]["rules_verdict"],
                     "llm": result["extra"].get("llm_verdict", "error"), "llm_guardrail": result["verdict"],
                     "tools_used": len(result["steps"]), "rules_seconds": round(rules_seconds, 4),
                     "seconds": round(time.time() - start, 1)})
        time.sleep(pause)
    table = pd.DataFrame(rows)
    ok = table[table["llm"] != "error"]                    # emails where the LLM answered
    comparison = pd.DataFrame([{"method": label, **metrics_of(ok, column)} for label, column in
                               [("Rules + ML", "rules"), ("LLM agent", "llm"), ("LLM agent + guardrail", "llm_guardrail")]])
    seconds = {"Rules + ML": ok["rules_seconds"].mean(),            # each method gets its own time per email
               "LLM agent": ok["seconds"].mean(), "LLM agent + guardrail": ok["seconds"].mean()}
    comparison["avg_seconds"] = comparison["method"].map(seconds)
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(config.DB_PATH.parent / "llm_comparison.csv", index=False)     # the web app shows this file
    table.to_csv(config.DB_PATH.parent / "llm_comparison_emails.csv", index=False)
    return comparison, table


def evaluate_sentiment():
    """Compare the Arabic word-list sentiment with the real label (from the star rating)."""
    reviews = load_reviews()
    lexicon = load_lexicon()
    reviews["guess"] = reviews["text"].apply(lambda text: guess_sentiment(text, lexicon))
    accuracy = (reviews["guess"] == reviews["sentiment"]).mean()
    confusion = pd.crosstab(reviews["sentiment"], reviews["guess"], rownames=["truth"], colnames=["guess"])
    return {"reviews": len(reviews), "accuracy": accuracy}, confusion
