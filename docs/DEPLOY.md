# Deploy Sentinel (free, Render)

Result: a public link like `https://sentinel-hagar.onrender.com` for the demo, README and CV.
The React app is already built into `frontend/dist`, so the server only needs Python.

## 1. Put the project on GitHub

1. Go to **github.com → New repository**. Name: `sentinel`. Public. Don't add a README (we have one).
2. In the VS Code terminal, inside the project folder:

```
git init
git add .
git commit -m "Sentinel: 4 agents, LangGraph orchestrator, FastAPI + React"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/sentinel.git
git push -u origin main
```

3. On GitHub, check that **`.env` is NOT there** and `frontend/node_modules` is NOT there (`.gitignore` keeps both out).
   Your API key must never be on GitHub. Check that **`frontend/dist` IS there**: that's the web app.

## 2. Deploy on Render

1. Go to **render.com** and sign in with GitHub.
2. **New → Web Service** → pick the `sentinel` repository.
3. Fill in:
   - Language: **Python 3**
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - Instance type: **Free**
4. **Environment variables** (this replaces `.env` on the server):

| Key | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.11.9` |
| `LLM_PROVIDER` | `gemini` |
| `GOOGLE_API_KEY` | your key |
| `DRY_RUN` | `true` |

5. Click **Create Web Service** and wait a few minutes for the libraries to install.

## 3. After it works

- Put the link at the top of `README.md` and in the LinkedIn post. `/docs` on the same link shows the API.
- Keep `DRY_RUN = true` online, so visitors can't make the app send real emails.
- The free plan sleeps after 15 minutes without visitors; the first visit after that takes ~1 minute. Open it before a demo.
- The online memory resets when the app restarts. That's fine for a demo.

## If the deploy fails

Open the service → **Logs**. The last red lines say what's wrong.
The usual cause is a library missing from `requirements.txt`.

## If you changed the design

Rebuild the web app before you push: `cd frontend`, `npm run build`, then `git add frontend/dist` and push.
