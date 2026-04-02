# Compliance Audit Tool - Frontend

React frontend for evaluating healthcare policy documents against DHCS audit questionnaires.

## How It Works

1. **Login** with credentials configured on the backend (`AUTH_USERNAME`, `AUTH_PASSWORD`).
2. **Upload** a questionnaire PDF. The backend extracts structured questions and returns them.
3. **Evaluate** questions individually or all at once. Each question is checked against policy documents via RAG and returns a met/not_met status with supporting evidence and citations.

## Prerequisites

- Node.js 18+
- Backend running (see `backend/README.md`)

## Setup

```bash
cd frontend
npm install
```

Create a `.env` file:

```
VITE_API_URL=http://localhost:8000
```

To point at the deployed backend:

```
VITE_API_URL=my-url.com
```

## Running

```bash
npm run dev
```

The app is available at `http://localhost:5173`.

## Building

```bash
npm run build
npm run preview
```

## Project Structure

```
frontend/
  src/
    api.js                     # API client (health, upload, evaluate)
    App.jsx                    # Router, providers, toast notifications
    main.jsx                   # Entry point
    index.css                  # Global styles
    context/
      AuthContext.jsx          # In-memory credential storage
    pages/
      LoginPage.jsx            # Username/password form
      UploadPage.jsx           # Drag-and-drop PDF upload
      ResultsPage.jsx          # Question list, evaluation, evidence display
```

## Deployment (Vercel)

1. Push to GitHub
2. Import the repository in [Vercel](https://vercel.com/new)
3. Set the following build settings:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
4. Add the environment variable:
   - `VITE_API_URL` = 'my-url.com'
5. Deploy

Vercel handles SPA routing automatically. For other hosts, configure rewrites so all paths serve `index.html`.

## Tech Stack

- **Framework:** React 19
- **UI:** Adobe React Spectrum
- **Bundler:** Vite
- **Routing:** React Router