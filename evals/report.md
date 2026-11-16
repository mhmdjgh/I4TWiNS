# Routing evaluation report

- Model: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- Date: 2026-11-16 09:20 UTC
- Cases: 15
- **Skill-detection accuracy: 87%** (13/15)
- 1 case(s) failed with a provider error and were not routed; accuracy on the 14 routed cases: 13/14 (93%)
- Multi-skill mode (sequential/parallel) correct: 3/3

## By category

| Category | Correct |
|---|---|
| clear | 7/7 |
| multi | 4/4 |
| ambiguous | 1/2 |
| no_skill | 1/2 |

## Per skill

| Label | Precision | Recall | Support |
|---|---|---|---|
| calculator | 1.00 | 1.00 | 4 |
| clarify | 1.00 | 0.50 | 2 |
| general_chat | 1.00 | 0.60 | 5 |
| summarizer | 0.75 | 1.00 | 3 |
| translator | 1.00 | 1.00 | 5 |

## Cases

| | ID | Expected | Predicted | Mode | Conf. | Latency |
|---|---|---|---|---|---|---|
| ✅ | `clear-chat-en` | general_chat | general_chat | single | 0.99 | 2.1s |
| ✅ | `clear-chat-fa` | general_chat | general_chat | single | 0.98 | 2.1s |
| ✅ | `clear-calc-fa` | calculator | calculator | single | 0.99 | 1.2s |
| ✅ | `clear-calc-en` | calculator | calculator | single | 0.99 | 1.9s |
| ✅ | `clear-summarize-fa` | summarizer | summarizer | single | 0.98 | 1.2s |
| ✅ | `clear-translate-en-fa` | translator | translator | single | 0.99 | 1.1s |
| ✅ | `clear-translate-fa-en` | translator | translator | single | 0.99 | 1.3s |
| ✅ | `multi-summarize-translate-fa` | summarizer → translator | summarizer → translator | sequential | 0.96 | 1.4s |
| ✅ | `multi-translate-calc-en` | translator → calculator | translator → calculator | parallel | 0.95 | 1.3s |
| ✅ | `multi-tldr-in-french-en` | summarizer → translator | summarizer → translator | sequential | 0.96 | 1.5s |
| ✅ | `multi-greeting-calc-fa` | general_chat → calculator | calculator | single | 0.98 | 1.5s |
| ✅ | `ambiguous-translate-no-text` | clarify | clarify | single | 0.90 | 1.0s |
| ❌ | `ambiguous-summarize-no-text-fa` | clarify | summarizer | single | 0.95 | 1.2s |
| ✅ | `no-skill-poem-en` | general_chat | general_chat | single | 0.95 | 1.8s |
| ❌ | `no-skill-math-history-fa` | general_chat | — (error) | - | 0.00 | 8.5s |
