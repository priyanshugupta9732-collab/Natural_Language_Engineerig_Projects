Problem 3 - LLM prompts and output (Informationslinguistik 1, WS 2026/27)

Files
- manual_variant1_no_context.txt    : prompt of variant 1 (no contextual information) incl. the 25 reviews
- manual_variant2_with_context.txt  : prompt of variant 2 (with the 385 grouped labels from Problem 1) incl. the same 25 reviews
- llm_variant1_output.json          : answer of the LLM to variant 1
- llm_variant2_output.json          : answer of the LLM to variant 2

Setup
- Model: [FILL IN model name and version]
- Interface: chat interface (not the API), date: [FILL IN, e.g. 1 November 2026]
- Each variant was run in a separate new chat; the prompt file was attached (variant 2) / pasted (variant 1) [adjust if different].
- Data: 25 randomly chosen reviews (120 to 420 characters) from reviews.txt.
- A first attempt at variant 2 failed because the long prompt was truncated when pasted; it was repeated and only the second, complete run is reported.
- The outputs are the model answers as received. The chat showed typographic quotation marks; they were replaced by plain quotation marks so that the files are valid JSON. No content was changed.
