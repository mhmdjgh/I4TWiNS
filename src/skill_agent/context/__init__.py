"""Keeping every model call inside its context window.

* shortlist - the router sees O(top_k) skill cards, not O(number of skills)
* tokens    - token estimation and head/tail excerpts for routing long messages
* budget    - output allowance per skill and input room per call
* chunking  - splitting long texts for map-reduce summarization and chunked translation
"""
