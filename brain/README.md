# Eldric Brain

This folder is the source of truth for Eldric's static knowledge brain.

The database stores users, conversations, test state, payments, and user memory.
The database should not store the curated general knowledge base.

## Brain Layout

```text
brain/
  knowledge/
    attachment/
    relationships/
    polarity/
    somatics/
  memory/
  system/
```

## Two Brain Model

- Knowledge brain: curated articles, concepts, practices, scripts, and source notes.
- User memory brain: personal facts, patterns, goals, and relationship context extracted from conversations.

The knowledge brain lives in files and is indexed by the backend.
The user memory brain lives in the database because it is private, dynamic product data.

