# Sentinel Demo Co. AI Cost Policy (excerpt)

## Monthly budget
Every team has a monthly AI budget. Above 80% of the budget is a Warning; above 100% is Critical and the CTO must be told.

## Choosing a model
Use the cheapest model that is good enough for the task.
Short, simple answers (classification, short code completions, yes/no) should use a small model.
Long reasoning, legal or medical answers may use a large model.
Moving a feature to another model needs approval from the CTO and a quality test on real examples first.

## Long prompts
Very long prompts (more than 4,000 tokens) should use prompt caching or be shortened.
Turning on prompt caching needs approval from the platform team.

## Spending limits
Every API key must have a monthly spending limit. Setting or changing a limit needs approval from the CTO.

## Reports
The CTO gets a short cost report: monthly cost, budget used, the biggest waste, and the top saving with its dollar amount.
