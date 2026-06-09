# Open Models That Handle MCP Tool Calls Well (2026)

## Strong performers (tool calling)
- **Qwen3 series** (0.6B–32B): Best-in-class tool calling for size. Qwen3.5:2b is a strong demo model.
- **Phi-4 mini**: Microsoft's structured-output fine-tune. Reliable JSON compliance.
- **Llama 3.1/3.2**: Meta's function calling fine-tunes. 8B works well with careful prompting.
- **Mistral 7B Instruct v0.3**: Early adopter of tool use, still holds up.
- **Granite 3.x**: IBM's enterprise models, strong schema compliance.

## Needs careful prompting
- **Gemma 2/3**: Good reasoning, inconsistent JSON formatting without schema constraints.
- **DeepSeek-R1 distills**: Strong reasoning, tool call format can drift.

## Avoid for tool calling
- General chat fine-tunes without explicit function-calling training
- Older Llama 2-era models
- Very small (<1B) models without specific tool-call fine-tuning

## Key insight
The quality delta between structured-output fine-tunes and general chat models
is larger than the quality delta between 7B and 70B parameters.
Pick the right fine-tune before scaling up model size.
