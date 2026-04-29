# Torn-AgentPay Protocol Bundle

This directory packages the published AimiPay protocol schemas and conformance references.

Contents:

- `schemas/`: versioned JSON Schema files
- `PROTOCOL_REFERENCE.md`: canonical protocol behavior
- `discovery.md`: manifest and discovery object reference
- `THIRD_PARTY_IMPLEMENTER_GUIDE.md`: implementation guidance
- `BUYER_IMPLEMENTER_GUIDE.md`: buyer-side integration guidance
- `HOST_IMPLEMENTER_GUIDE.md`: AI host and MCP integration guidance
- `AI_HOST_PLAYBOOK.md`: host-side default tool flow, skill-only behavior, and recovery actions
- `COMPATIBILITY_POLICY.md`: public compatibility commitments
- `CONFORMANCE_CHECKLIST.md`: manual validation checklist
- `aimipay.capabilities.json`: AI-facing capability manifest

Suggested validation flow:

1. materialize your manifest JSON
2. materialize your discover JSON
3. optionally materialize your attestation verification report
4. run `python -m ops_tools.conformance_check --manifest-file <manifest.json> --discover-file <discover.json> --attestation-file <attestation.json>`
