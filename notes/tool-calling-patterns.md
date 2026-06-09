# Tool Calling Patterns for Small Models

## Pattern 1: Describe with examples
Small models rely heavily on the description field.
Never leave it vague. Include concrete examples in the description itself.

Bad:  "Gets weather for a city"
Good: "Gets current weather for a city. city param must be a city name, e.g. 'Mumbai', 'Berlin', 'New York'. Returns temp in Celsius."

## Pattern 2: Constrain the schema
Use JSON Schema constraints to reduce the model's search space.
- `pattern` for strings that must match a format
- `enum` for categorical values
- `minimum`/`maximum` for numbers
- `examples` array where supported

## Pattern 3: Single responsibility
Each tool should do exactly one thing.
Multi-purpose tools confuse 7B-class models reliably.

Bad:  search_and_summarize(query, format, max_results)
Good: search_notes(query) → separate summarize(text) call

## Pattern 4: Negative space
Tell the model what the tool does NOT do.
This prevents wrong tool selection when prompts are ambiguous.

"Does NOT search the web. Does NOT return forecasts."

## Pattern 5: Tool descriptions as examples
The first sentence of a description should be usable as a one-line example
of when to invoke the tool. Models use this for tool selection.
