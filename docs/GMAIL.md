# Connecting your real Gmail

Tiles ships two Gmail connectors:

- **`gmail`** — a **mock** with fake data. Zero setup; the `Inbox Summary` and
  `Reply Drafter` tiles use it so you can learn the flow offline.
- **`gmail-live`** — the **real** connector (`Inbox Summary (live)`,
  `Reply Drafter (live)`). It reads/sends your actual mail over the Gmail REST
  API using Google OAuth.

Reading Gmail requires a **Google Cloud OAuth app** — that's Google's rule, not
something Tiles can skip. It's a one-time setup; after it, connecting is just
"paste, Authorize" from the board.

> Heads up: this connector's live calls were built to the Gmail v1 API but
> couldn't be tested against a real account during development. Expect to be the
> first real run — if a field looks off, it's in `connectors/gmail-live/adapter.py`.

## 1. Create a Google OAuth client (once)

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and create
   (or pick) a project.
2. **APIs & Services → Library →** enable the **Gmail API**.
3. **APIs & Services → OAuth consent screen:** choose **External**, fill the
   basics, and add yourself under **Test users** (so you don't need Google's full
   app verification while testing). Add the scopes
   `.../auth/gmail.readonly` and `.../auth/gmail.send`.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID:**
   - Application type: **Web application**
   - **Authorized redirect URI:** `http://127.0.0.1:8000/api/oauth/callback`
     (match the host/port you run `tiles up` on)
5. Copy the **Client ID** and **Client secret**.

## 2. Connect it from the board

Run `tiles up` (not `--echo`), open the board, then on **Gmail (live)** click
🔌 → **⚙**:

1. **OAuth client ID** — paste your client ID, click **Save**.
2. **API keys → `GOOGLE_CLIENT_SECRET`** — paste your client secret, **Save keys**.
3. Click **Authorize** — a Google window opens; pick your account and consent.
   The token is stored in `oauth.local.yaml` (gitignored).

Now tap **Inbox Summary (live)** or **Reply Drafter (live)**. Reply Drafter
queues every send for your approval (draft tier) — nothing is sent until you
approve it.

## Notes

- **Tokens refresh automatically.** Because the connector requests
  `access_type=offline`, Google returns a refresh token; Tiles refreshes the
  access token when it expires (it's re-checked each time you activate a tile).
- **Restricted scopes.** `gmail.readonly` / `gmail.send` are "restricted" scopes.
  In **testing** mode they work for your own (test-user) account. Publishing the
  app for others requires Google's verification — out of scope for local use.
- **Security.** Your client secret lives only in `secrets.local.yaml` and the
  OAuth token only in `oauth.local.yaml` — both gitignored, never in a manifest.
- **Make it the only Gmail?** If you don't want the mock, delete the `gmail`
  connector + its `inbox-summary`/`reply-drafter` tiles (or rename `gmail-live`
  to `gmail` and repoint those tiles).
