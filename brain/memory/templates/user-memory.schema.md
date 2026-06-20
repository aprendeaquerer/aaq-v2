# User Memory Schema

```json
{
  "type": "emotional_trigger",
  "summary": "Delayed replies from partner make the user feel abandoned.",
  "curated_summary": "You have noticed that delayed replies can make you feel unsafe or abandoned.",
  "visibility": "user_visible",
  "sensitivity": "normal",
  "confidence": 0.84,
  "status": "active",
  "source_message_ids": ["msg_123"],
  "metadata": {
    "partner_name": "Ana",
    "domain": "attachment"
  }
}
```

## Field Meanings

- `summary`: internal concise memory used for retrieval.
- `curated_summary`: gentle user-facing wording.
- `visibility`: `user_visible`, `internal`, or `hidden`.
- `sensitivity`: `normal`, `sensitive`, or `high`.
- `confidence`: 0.0 to 1.0.
- `status`: `candidate`, `active`, `archived`, or `rejected`.

