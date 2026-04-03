# Child Development Assessment Frontend

This is the frontend application for the Child Development Assessment Agent.

## Tech Stack
- React
- TypeScript
- Vite
- TailwindCSS
- React Hook Form
- Shadcn/UI (Custom implementation)

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Open your browser at `http://localhost:5173`.

## Configuration
The frontend is configured to proxy API requests to `http://127.0.0.1:8000`. If your backend runs on a different port, update `vite.config.ts`.
