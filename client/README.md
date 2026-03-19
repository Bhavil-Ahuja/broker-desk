# Broker Chat – React client

Separate dashboards with Socket.IO for real-time updates.

- **Lead app**: `/` — Login/register, chat, recommended properties. Real-time when broker sends a message.
- **Broker dashboard**: `/broker` — Leads list, conversation, pending approvals. Real-time when a lead sends or a new approval is created.

## Run

1. Start the Flask API (with Socket.IO) on port 5001.
2. From this folder:

```bash
npm install
npm run dev
```

3. Open http://localhost:3000 (lead) or http://localhost:3000/broker (broker).

Vite proxies `/api` and `/socket.io` to port 5001, so the React app talks to the same backend.

## Build

```bash
npm run build
```

Serve the `dist` folder and set the API base URL for production (e.g. env var) if needed.
