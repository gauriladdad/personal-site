# System Architecture

## Overview

Kids News uses a serverless static architecture:
- Static frontend
- Static data
- One scheduled backend job
- No runtime backend services

This keeps costs near zero and removes entire classes of failure.

## Architecture Diagram (Mental Model)

```
EventBridge (daily)
        ↓
AWS Lambda (Python)
        ↓
   Gemini AI
        ↓
     AWS S3
        ↓
Cloudflare Pages
        ↓
   User Browser

```

## Data Layer — AWS S3 
S3 acts as both database and API.

### Files
| File              | Purpose                    |
| ----------------- | -------------------------- |
| `index.json`      | Latest date + archive list |
| `YYYY-MM-DD.json` | News for that day          |

### Access
- Public read
- Served directly to browsers
- Cache-controlled (low TTL during development)

## Backend — AWS Lambda

### Role

A daily ETL job:
- Extract → Transform → Publish
No requests come into Lambda from users.

## Feed Ingestion

Sources currently include:

- BBC World News (RSS)
- ScienceDaily (RSS)
- Government of Canada (Atom, children audience)

Feeds are fetched sequentially to avoid timeouts and rate limits.

## AI Processing

Gemini is used *only after de-duplication*.

For each article:
- Reads full article text
- Decides:
  - suitable (true/false)
  - ageBucket
  - flags[]
- Generates a neutral summary

### Safety Rules
- If violence, war, adult politics, or crime → exclude younger ages
- If unsure → exclude entirely

## API Quota Strategy

Gemini free tier limits:
- ~20 calls / day / project

#### Solution:

- Multiple Google Cloud projects
- Keys provided as a comma-separated list
- Lambda rotates keys automatically
- If all keys exhaust:
  - Publishes partial results
  - Updates index.json
  - Exits cleanly

The site never goes down.

## Frontend — Astro + Cloudflare

### Rendering Model

- Static HTML shell
- Client-side fetch of JSON
- DOM rendering (no framework)

### State

- currentAge (localStorage)
- currentCategory (in-memory)

### Why No SSR

- News updates independently of site deploys
- Static hosting is cheaper, faster, simpler

## Failure Modes (Designed For)

| Failure               | Outcome                      |
| --------------------- | ---------------------------- |
| Gemini quota hit      | Partial news published       |
| Feed timeout          | Category empty               |
| Lambda timeout        | Previous day remains visible |
| Frontend deploy fails | Data still accessible        |

No single failure breaks the site.

## Future Considerations (Not Implemented)

- DynamoDB (only if user features are added)
- Paid Gemini tier (if volume increases)
- Per-story images (carefully curated)
- Optional teacher / classroom mode

## Non-Goals

- User accounts
- Comments
- Personalization
- Real-time updates
- Social sharing optimization
