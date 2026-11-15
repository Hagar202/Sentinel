"""The Arabic Voice-of-Customer agent (an LLM agent with tools): read real Arabic customer reviews -> find what
customers complain about -> tell the product manager (in English and Arabic).

Data: 4,272 real product reviews from souq.com (labelled from the star rating: 1 positive, 0 neutral, -1 negative),
and an Arabic sentiment word list from the same research project.
The LLM READS the Arabic reviews itself and finds the complaint topics (generative), then checks every topic on
ALL the reviews with a counting tool. Guardrail: the numbers come from counting the data, never from the LLM.
"""
from typing import Literal

import pandas as pd
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from . import config, memory
from .llm import get_llm, run_agent
from .results import Action, make_result, needs_approval

REVIEWS = config.ROOT / "datasets" / "arabic_product_reviews.csv"
LEXICON = config.ROOT / "datasets" / "arabic_sentiment_lexicon.csv"

# Words that point to each complaint topic
TOPICS = {
    "Bad quality": ["جودة", "الجودة", "خامة", "الخامة", "رديء", "ردئ", "رديئ", "سيء", "سيئ", "تقليد", "مضروب", "عيب", "معيوب"],
    "Not working / broken": ["لا يعمل", "لا تعمل", "لاتعمل", "لايعمل", "ما يشتغل", "مش شغال", "عطل", "خربان", "مكسور", "كسر", "توقف"],
    "Price too high": ["غالي", "غالى", "غاليه", "غالية", "مبالغ", "مكلف", "لا يستحق", "لايستحق", "ما يستاهل", "مايستاهل", "سعره عالي", "السعر عالي", "سعرها غير مناسب", "سعره غير مناسب", "السعر غير مناسب"],   # "سعر" alone is not a complaint ("سعرها مناسب")
    "Delivery": ["توصيل", "التوصيل", "الشحن", "وصلت", "تأخير", "تاخير", "متأخر", "المندوب", "استلام"],
    "Battery / heat": ["بطارية", "البطارية", "البطاريه", "سخونة", "سخونه", "حرارة", "يسخن"],
    "Returns / refunds": ["ارجاع", "إرجاع", "استرجاع", "استرداد", "استبدال", "رجعت"],
}
WONT_BUY_AGAIN = ["لا انصح", "لا أنصح", "لانصح", "مش هشتري", "لن اشتري", "لن أشتري", "ندمت", "خسارة", "لا تشتري", "لن اتعامل"]


# ---------- 1. Get the data ----------
def load_reviews():
    reviews = pd.read_csv(REVIEWS).dropna(subset=["text"])
    reviews["text"] = reviews["text"].astype(str)
    reviews["sentiment"] = reviews["polarity"].map({1: "positive", 0: "neutral", -1: "negative"})
    return reviews


def load_lexicon():
    """Arabic sentiment words: {'روعه': 1, 'رديئه': -1, ...}"""
    lexicon = pd.read_csv(LEXICON)
    return dict(zip(lexicon["ngram"].astype(str), lexicon["polarity"]))


# ---------- 2. Understand a review ----------
def find_topics(text):
    return [topic for topic, words in TOPICS.items() if any(word in text for word in words)]


def guess_sentiment(text, lexicon):
    """Add +1 for every positive word and -1 for every negative word in the review."""
    score = sum(polarity for word, polarity in lexicon.items() if word in text)
    return "positive" if score > 0 else "negative" if score < 0 else "neutral"


def wont_buy_again(text):
    return any(phrase in text for phrase in WONT_BUY_AGAIN)


def decide(score):
    if score >= 5:
        return "critical"
    if score >= 2:
        return "warning"
    return "ok"


SYSTEM_PROMPT = """You are Sentinel's Voice-of-Customer analyst. The reviews are real Arabic product reviews.
Read negative reviews with your tools, find the main complaint topics yourself, then CHECK each topic on all the
reviews with count_reviews (give the Arabic words people use, with spelling variants).
Decide the severity (critical, warning or ok) for the product team and propose actions.
Only use numbers that your tools returned."""


class Complaint(BaseModel):
    topic: str = Field(description="Short English name, e.g. 'Bad quality'")
    words: list[str] = Field(description="Arabic words customers use for it, with spelling variants")
    example: str = Field(description="One real review (in Arabic) that shows it")


class VocReport(BaseModel):
    severity: Literal["critical", "warning", "ok"]
    summary: str = Field(description="3 sentences in English for the product manager: main problems, what to fix first")
    summary_ar: str = Field(description="The same summary in Arabic")
    complaints: list[Complaint]
    actions: list[Action]


# ---------- 3. The rule checks (the guardrail, and the offline answer) ----------
def rule_checks(reviews, unhappy):
    findings = []
    counts = unhappy["topics"].explode().value_counts()
    for topic, count in counts.items():
        share = count / len(unhappy) * 100
        if share >= 10:
            findings.append({"reason": f"{topic}: {count} unhappy customers ({share:.0f}% of complaints)", "points": 2})
        elif share >= 5:
            findings.append({"reason": f"{topic}: {count} unhappy customers ({share:.0f}% of complaints)", "points": 1})

    negative_share = len(unhappy) / len(reviews) * 100
    if negative_share >= 15:
        findings.append({"reason": f"{negative_share:.0f}% of {len(reviews):,} reviews are negative", "points": 2})

    leaving = reviews[reviews["leaving"]]
    if len(leaving) >= 20:
        findings.append({"reason": f"{len(leaving)} customers tell others not to buy (e.g. 'لا انصح')", "points": 3})
    return findings, counts, negative_share, leaving


# ---------- 4. The tools (the agent decides which ones to call) ----------
def count_matching(reviews, words, sentiment="negative"):
    """How many reviews (of this sentiment) contain at least one of the words."""
    rows = reviews if sentiment == "all" else reviews[reviews["sentiment"] == sentiment]
    words = [w for w in words if w.strip()]
    return rows[rows["text"].apply(lambda text: any(w in text for w in words))] if words else rows.iloc[0:0]


def make_tools(reviews):
    @tool
    def review_stats(sentiment: Literal["all", "negative", "neutral", "positive"] = "all") -> str:
        """How many reviews there are, and the share of each sentiment (from the real star rating)."""
        shares = reviews["sentiment"].value_counts()
        if sentiment != "all":
            return f"{shares.get(sentiment, 0):,} {sentiment} reviews of {len(reviews):,} ({shares.get(sentiment, 0) / len(reviews):.0%})"
        return f"{len(reviews):,} reviews: " + ", ".join(f"{s} {n:,} ({n / len(reviews):.0%})" for s, n in shares.items())

    @tool
    def read_reviews(sentiment: Literal["negative", "neutral", "positive"] = "negative", n: int = 25,
                     contains: str = "") -> str:
        """Read real reviews (Arabic). Optional: only reviews that contain a word."""
        rows = reviews[reviews["sentiment"] == sentiment]
        if contains:
            rows = rows[rows["text"].str.contains(contains, regex=False)]
        sample = rows.sample(min(n, 40, len(rows)), random_state=1) if len(rows) else rows
        return "\n".join("- " + text[:220] for text in sample["text"]) or "No reviews found."

    @tool
    def count_reviews(words: list[str], sentiment: Literal["all", "negative", "neutral", "positive"] = "negative") -> str:
        """Count ALL reviews that contain at least one of these Arabic words (to check a complaint topic on the data)."""
        found = count_matching(reviews, words, sentiment)
        total = len(reviews) if sentiment == "all" else int((reviews["sentiment"] == sentiment).sum())
        examples = " | ".join(found["text"].head(2).str[:120])
        return f"{len(found):,} of {total:,} {sentiment} reviews contain {words}. Examples: {examples}"

    return [review_stats, read_reviews, count_reviews]


# ---------- 5. The agent ----------
def analyze_reviews(reviews=None, llm=None, use_llm=True, remember=True):
    reviews = reviews if reviews is not None else load_reviews()
    reviews = reviews.assign(topics=reviews["text"].apply(find_topics), leaving=reviews["text"].apply(wont_buy_again))
    unhappy = reviews[reviews["sentiment"] == "negative"]

    # A. Rule checks (word lists): the answer when there is no LLM
    findings, counts, negative_share, leaving = rule_checks(reviews, unhappy)
    score = sum(f["points"] for f in findings)
    verdict, steps, decided_by, extra = decide(score), [], "rules (offline)", {"rules_verdict": decide(score)}
    top = counts.index[0] if len(counts) else "none"
    summary = (f"{len(reviews):,} real Arabic reviews: {negative_share:.0f}% negative. "
               f"Top complaint: {top}. {len(leaving)} customers say they don't recommend the product.")
    actions = [{"action": "Send the feedback report to the product manager", "needs_approval": False}]
    if len(counts):
        actions.append({"action": f"Open a quality ticket for '{top}' with the supplier", "needs_approval": True})
    if len(leaving):
        actions.append({"action": f"Ask customer service to contact the {len(leaving)} customers who don't recommend us",
                        "needs_approval": True})

    # B. The LLM agent reads the Arabic reviews and finds the topics itself
    llm = llm or (get_llm() if use_llm else None)
    if llm:
        try:
            task = (f"We have {len(reviews):,} real Arabic product reviews from souq.com. "
                    "What do unhappy customers complain about, how big is each problem, and what should we fix first?")
            report, steps = run_agent(llm, SYSTEM_PROMPT, task, make_tools(reviews), VocReport)
            verdict, summary, decided_by = report.severity, report.summary, "LLM agent"
            # C. Guardrail: every number comes from counting the data; topics with no matching review are dropped
            complaints = []
            for c in report.complaints[:6]:
                found = count_matching(reviews, c.words)
                if len(found):
                    complaints.append({"topic": c.topic, "count": len(found), "words": c.words, "example": c.example})
            complaints.sort(key=lambda c: -c["count"])
            extra.update(llm_verdict=report.severity, summary_ar=report.summary_ar, complaints=complaints)
            actions = [{"action": "Send the feedback report to the product manager", "needs_approval": False}]
            actions += [{"action": a.action, "needs_approval": needs_approval(a)} for a in report.actions[:5]]
        except Exception as error:          # wrong key, no internet, free limit reached -> keep the rule-based answer
            summary += f" (LLM not used: {type(error).__name__}: {str(error)[:160]})"

    result = make_result("Arabic VoC", f"{len(reviews):,} Arabic customer reviews", verdict, score, findings, summary,
                         actions, steps, decided_by, extra)
    if remember:
        memory.save(result)
    return result
