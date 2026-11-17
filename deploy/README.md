# Hosting the dashboard

This runs the dashboard on a Linux server behind [Caddy](https://caddyserver.com/), which gets an
HTTPS certificate for your domain and renews it on its own. You need a server with Docker and Docker
Compose, ports 80 and 443 open, and a domain whose DNS A record points at the server.

## 1. Get the code onto the server

```bash
git clone https://github.com/mhmdjgh/I4TWiNS.git skill-agent
cd skill-agent
cp .env.example .env
```

## 2. Fill in `.env`

The same file configures both containers. At minimum:

```bash
LLM_API_KEY=...            # key for your provider
DOMAIN=agent.example.com   # the domain pointing at this server
DASHBOARD_PASSWORD=...     # strongly recommended on a public server
```

With the defaults the agent uses OpenRouter's free tier. Any OpenAI-compatible provider works by
changing the provider settings, for example:

```bash
LLM_BASE_URL=https://api.your-provider.com/v1
LLM_MODEL=the-model-id-on-that-provider
LLM_FALLBACK_MODEL=                # empty disables the fallback
LLM_REASONING_PARAM=openai         # if the provider expects `reasoning_effort`
```

Keep `.env` on the server only. It is listed in `.gitignore` and `.dockerignore`, so it never ends
up in the repository or in the image.

## 3. Start it

```bash
docker compose up -d --build
```

The first start takes a minute while Caddy fetches the certificate. Then open `https://DOMAIN`.

## Day to day

```bash
docker compose logs -f app           # application logs
git pull && docker compose up -d --build   # update to the latest version
docker compose down                  # stop everything
```

## Why a password

On a public server every prompt is paid for by the key in `.env`. With `DASHBOARD_PASSWORD` set,
the dashboard shows a sign-in screen first and nothing reaches the model until the right password
is entered. It's compared in constant time and only kept for the browser session.
