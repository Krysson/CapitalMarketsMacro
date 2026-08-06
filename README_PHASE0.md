PHASE 0 — DEPLOY & VERDICT (15 minutes)

WHAT THIS IS
  A two-file FastAPI stub whose only job is answering the migration
  spec's go/no-go gate from Render's actual IP: which Yahoo
  endpoints answer, whether option chains carry real OI, and
  whether get_shares_full varies (i.e., whether the v4.9.2 flow fix
  holds on Render too). One URL returns the whole verdict.

STEP 1 — put the files in the repo
  In CapitalMarketsMacro on main, create a top-level api/ folder
  and add the two files from this zip:
      api/main.py
      api/requirements.txt
  Nothing existing moves — Streamlit ignores the new folder. Commit.

STEP 2 — deploy on Render
  render.com → New → Web Service → connect the CapitalMarketsMacro
  repo, then:
      Root Directory:   api
      Runtime:          Python 3
      Build Command:    pip install -r requirements.txt
      Start Command:    uvicorn main:app --host 0.0.0.0 --port $PORT
      Instance Type:    Free
  Create the service and wait for "Live" (first build ~2-4 min).

STEP 3 — run the battery
  Open in a browser:
      https://<your-service>.onrender.com/            (hello)
      https://<your-service>.onrender.com/api/health  (up check)
      https://<your-service>.onrender.com/probe       (THE VERDICT)
  If the first load hangs ~30-60s, that's the free tier waking from
  sleep — normal; reload.

STEP 4 — paste the /probe JSON back to Claude
  The verdict block maps directly onto the architecture decision:
      go_no_go: GO       → v5 serves live quotes/chains direct
      go_no_go: PARTIAL  → chart pipe works; quotes/chains ride the
                           accrual + cache-with-timestamp pattern
      go_no_go: NO-GO    → all market data rides the data branch /
                           Supabase (the bot pattern, everywhere)
  Also decisive inside the legs:
      option_chain.oi_zeroed = true  → Render sees the same OI
                                       degradation the app saw 06-Aug
      shares_full.static = true      → the shares fix needs a
                                       different source on Render

NOTES
  Every leg fails soft with a named error — a NO-GO renders as
  readable JSON, never a 500. CORS is wide open for Phase 0 so the
  lovable scaffold can call this URL later; it gets locked to real
  origins in Phase 4. The pinned fastapi/uvicorn pair is deliberate
  (the 05-Aug Streamlit outage was unbounded ranges; the v5 line
  starts pinned).
