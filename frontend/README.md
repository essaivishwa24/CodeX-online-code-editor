# CodeX frontend

React + Vite frontend for the CodeX online code editor. It supports Python, JavaScript, and sandboxed HTML/CSS previews with a responsive developer-tool interface.

## Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite development and preview servers proxy `/api` requests to `http://127.0.0.1:8010` without changing the request path.

The default API base URL is empty, so Run sends a relative `POST /api/run` request through the Vite proxy. To point the frontend at a separately hosted backend, copy `.env.example` to `.env` and set:

```text
VITE_API_BASE_URL=http://127.0.0.1:8010
```

The execution request is `POST /api/run` with this JSON body:

```json
{
  "language": "python",
  "code": "print('Hello from CodeX!')"
}
```

## Production build

```bash
npm test
npm run build
npm run preview
```

The production assets are written to `dist/`. Configure `VITE_API_BASE_URL` at build time when the API is hosted on a different origin.

## Browser-side safety

HTML/CSS preview code is placed in an iframe with a restrictive `sandbox`, no `allow-scripts` or `allow-same-origin` capability, no referrer, and an injected Content Security Policy. Python and JavaScript are never evaluated by the browser; they are sent to the backend execution service.
