# GitHub and website deployment

Status: prepared, **NOT DEPLOYED**. GitHub and Railway were not connected; the browser was signed out of GitHub. No repository push, cloud resource creation or public URL has been verified. Local Docker was unavailable, so the combined Linux image remains unbuilt/untested.

The application needs Python, PostgreSQL and a persistent upload/vector directory. GitHub Pages serves static files and cannot run this complete backend. Source can live in a private GitHub repository while Railway exposes the application through HTTPS.

## Prepared deployment

`deploy/Dockerfile` builds React and serves its output through FastAPI at the same origin. `STATIC_DIR` enables deep-link handling; unknown API routes remain 404. The image contains the exact pinned embedding model in `/app/model-cache`. A runtime volume must mount `/app/runtime`, containing private uploads and the Chroma index. Initial startup adjusts those three fixed directories, drops to user 10001, runs migrations, seeds fictional schemes, indexes sources, then starts one Uvicorn worker on the host's `PORT`.

`railway.toml` sets Dockerfile, health check, startup timeout and one replica. It does not create a database, volume, account, subscription or domain by itself. Linux resolution/build resource requirements have not been measured. Start with adequate memory for PyTorch/model loading and observe actual use before tuning; do not promise a free hosting tier can support it.

## Steps requiring connected accounts

1. Connect GitHub and Railway. Upload this project root into a new private repository; exclude `.env`, runtime data, test credentials, dependencies and browser traces as the supplied ignore files specify.
2. Inspect the hosting account's plan/credits and approve any new recurring charge before provisioning.
3. Create the application service from that repository and add a private PostgreSQL service. Use a fresh cloud database and credentials, never copy the native demo database.
4. Configure `DATABASE_URL` from the private PostgreSQL service and generate a new random `JWT_SECRET` (48 bytes or more). Standard `postgresql://` URLs normalize to the Psycopg driver. Keep `LLM_MODE=local` and `DEMO_MODE=false`.
5. Add persistent storage mounted at `/app/runtime`. Keep one replica. Set `CORS_ORIGINS` to the exact deployed HTTPS origin once assigned. All frontend requests use the same origin.
6. Deploy, inspect build/startup logs without exposing secrets, and wait for `/api/health`. Generate a Railway HTTPS domain and test login, profiles, documents, local cited chat and admin ownership on that exact domain. Use synthetic information only.
7. Return the verified domain as the final website link. A generated domain alone does not prove the app works.

No admin account is public by default. Use `python -m app.cli create-admin` through an authorized private service shell when needed. Do not publish local demo credentials. Read KNOWN_LIMITATIONS.md before making any production claim; the app remains an academic demo.

Official deployment references inspected: [Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles), [Railway volumes](https://docs.railway.com/volumes), [configuration reference](https://docs.railway.com/config-as-code/reference), [current pricing](https://railway.com/pricing), [GitHub Pages limitations](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site).
