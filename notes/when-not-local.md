# When NOT to Go Local with MCP

## Go local when:
- Data must not leave the building (regulated industries, legal, medical)
- Offline / air-gapped deployment required
- Edge devices with intermittent connectivity
- Cost sensitivity at scale (no per-token billing)
- Latency requirements that cloud round-trips can't meet

## Don't go local when:
- Task requires frontier-class reasoning (complex multi-step planning, code generation at scale)
- Model needs to be updated frequently (local = manual upgrades)
- Team doesn't have GPU/NPU hardware to run models adequately
- The "private data" argument is really just procurement friction
- You need > 32K context reliably on complex tasks

## The honest benchmark
Run your actual task against a local 7B model and your cloud model.
Measure pass rate on tool calls, answer quality, latency.
If local is within 20% on your specific workload — go local.
If it's 50% worse, figure out if fine-tuning or a larger local model
closes the gap before writing off the local approach entirely.

## The hybrid pattern
Local model for tool selection + data retrieval.
Cloud model for final synthesis / complex reasoning.
Keeps sensitive retrieval local, uses cloud only on already-retrieved context.
