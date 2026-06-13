# Reply Drafter

A **draft**-tier reference tile. Reads your inbox, drafts a reply with the brain,
and **proposes** sending it. Nothing is sent automatically — the send queues for
your approval.

## What it demonstrates

- **The propose → gate → approve flow.** `run` returns a `send_message` action
  flagged `side_effect=True`. Under the `draft` tier the permission gate queues
  it; you approve it (the runtime then executes the send) or reject it.
- **Many tiles, one connector.** It binds the same `gmail` connector as the
  read_only Inbox Summary tile — the connection is shared, the agents differ.
- **Allow-list vs tier.** It allow-lists `send_message` (so it *may* propose a
  send) but its tier (`draft`) is what decides the send doesn't fire unattended.

## Try it

```
POST /api/tiles/reply-drafter/activate
POST /api/tiles/reply-drafter/run          -> result + a queued approval
GET  /api/approvals                         -> the pending send
POST /api/approvals/{id}/resolve {"approved": true}   -> executes the (mock) send
```

In v0 the send is a mock — it returns `{"status": "sent (mock)"}`. Wire a real
Gmail connector and the same flow sends real mail, still gated behind approval.
