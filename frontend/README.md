# Frontend Layer

The frontend is a SvelteKit chat client for the compliance backend.

## Features

- chat-style query interface
- provider and model selection
- source and language filters
- confidence indicator and cited provisions
- hardware guidance widget

## Run locally

```bash
cd frontend
npm install
npm run dev
```

Set `PUBLIC_API_BASE_URL` if the backend is not running on `http://localhost:8000`.
