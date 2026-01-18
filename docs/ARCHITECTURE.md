# System Architecture

## Overview

This document outlines the "Serverless Static" architecture used to host the Personal News Site with zero running costs (AWS Free Tier). It moves the site away from local data files to a cloud-hosted, automated pipeline.

## Current Architecture (Phase 1: S3 & Lambda)

### 1. Data Storage (AWS S3)

- **Service**: Amazon Simple Storage Service (S3).
- **Role**: Acts as the "Database" and "API" for the frontend.
- **Data Format**: Static JSON files.
  - `index.json`: Manifest of available dates.
  - `YYYY-MM-DD.json`: Daily news content.
- **Access**: Public Read access (via Bucket Policy/ACL) allows the frontend to fetch JSON directly via HTTP.
- **Cost**: Free Tier (First 5GB storage, 20k GET requests).

### 2. Frontend (Astro SPA)

- **Host**: Cloudflare Pages.
- **Mechanism**: Client-Side Fetching.
- **Flow**:
  1.  User visits `news.gattani.ca`.
  2.  Browser loads the static HTML/JS shell.
  3.  JavaScript fetches `S3_BUCKET_URL/index.json` to find the latest date.
  4.  JavaScript fetches `S3_BUCKET_URL/{date}.json` to render stories.
- **Advantage**: separating data from the build process means we don't need to rebuild the site to publish news.

### 3. Automation (AWS Lambda + EventBridge)

- **Service**: AWS Lambda (Python 3.12).
- **Role**: ETL (Extract, Transform, Load) worker with intelligent AI-powered filtering.
- **Trigger**: AWS EventBridge Scheduler runs the Lambda function **daily** (e.g., 7 AM UTC).

#### Pipeline V2: Two-Pass AI Filtering (Free-Tier Optimized)

The current pipeline implements a smart two-pass approach to maximize content while staying within Gemini's free tier limits:

**Phase 1: Feed Extraction & Filtering**

1. Fetch ALL entries from 6 BBC RSS feeds in parallel (~50-100 entries total)
2. Batch filter entries using Gemini (6 API calls, one per category)
   - Gemini evaluates: safety, educational value, relevance to kids
   - Returns indices of suitable stories (cheap operation - just titles/summaries)
3. Pre-filter results by category:
   - **Top Stories**: 10 max
   - **Technology**: 10 max
   - **Science**: 10 max
   - **Politics**: 10 max
   - **Health**: 5 max
   - **Canada**: 5 (AI-generated)

**Phase 2: Deep-Read Summarization**

1. Fetch full article text for filtered stories only (~18-20 stories remain)
2. Run expensive AI summarization on each:
   - Reads complete article content for accurate context
   - Strict fact-checking rules (no inferences, only stated facts)
   - Safety vetting for child-friendliness
3. Apply shared de-duplication across categories
   - Prevents same story appearing in multiple categories

**API Quota Management**

- **Daily Limit**: 20 Gemini API calls (free tier hard limit)
- **Actual Usage**: ~6 filtering + ~12-14 summarization = ~18-20 total ✅
- **Rate Limiting**: 500ms delay between calls (stays under 15 RPM soft limit)
- **Graceful Degradation**: If quota is exceeded mid-run, partial results are published to S3 instead of failing

**Cost Impact**

- **Before V2**: Manual selection, ~50 API calls/day = over quota
- **After V2**: Smart filtering, ~20 API calls/day = within free tier
- **Result**: 100% free, sustainable indefinitely on Gemini free tier

#### Graceful Failure Handling

When Gemini quota is exceeded:

1. Lambda captures all processed stories so far
2. Publishes partial JSON to S3 with completed categories
3. Updates index.json with current date
4. Returns HTTP 200 (success) instead of 500
5. Users see available stories; missing categories remain empty
6. Next day runs with fresh quota and completes processing

This ensures the site never goes dark due to API limits.

#### Multi-Project API Key Rotation (Scaling Beyond Free Tier)

To scale beyond the 20 calls/day free tier limit while staying free:

**Problem**: Single Google Cloud project = 20 API calls/day quota
**Solution**: Multiple Google Cloud projects with separate API keys

**Current Setup (Production)**

- **Project 1**: `Kids news project for Key 1`
  - API Key: `AIzaSyCesDHw_OKVxf691E29m7O3jgWvhBlm5Bs`
  - Quota: 20 calls/day
- **Project 2**: `Kids news project for Key 2`
  - API Key: `AIzaSyDyfHaXVcsxE2C0fQzovB9ZNNei68MGNzQ`
  - Quota: 20 calls/day

- **Total**: 40 calls/day across both projects ✅

**How It Works**:

1. Lambda environment variable contains comma-separated keys:

   ```
   GEMINI_API_KEYS = AIzaSyCesDHw_OKVxf691E29m7O3jgWvhBlm5Bs,AIzaSyDyfHaXVcsxE2C0fQzovB9ZNNei68MGNzQ
   ```

2. Code automatically rotates through keys on each API call
3. If one key's quota is reached, automatically switches to next key
4. If a key becomes invalid/expired, retries with next key

**Scaling Path**:

- 2 projects = 40 calls/day (current setup)
- 3 projects = 60 calls/day (add one more project)
- Beyond that = Upgrade to paid tier ($5-20/month for unlimited)
- **Cost**: Free Tier (512 MB memory, ~2-3 minute runtime per day)

## Future Roadmap (Phase 2: Database & IaC)

The following improvements are planned to scale the system and introduce professional Cloud Engineering practices.

### 1. Database (DynamoDB)

- **Why**: Replacing S3 JSON files with a real database allows for:
  - Querying by category, date range, or keywords.
  - Storing user interactions (likes/bookmarks) in the future.
- **Design**:
  - **Table**: `NewsStories` (Partition Key: `Date`, Sort Key: `StoryId`).
  - **API**: Requires an **API Gateway** in front of Lambda to query DynamoDB, as browsers cannot query DynamoDB directly securely.

### 2. Infrastructure as Code (IaC)

- **Why**: Clicking through the AWS Console is prone to error and hard to replicate.
- **Tool**: **Terraform** or **AWS SAM**.
- **Goal**: Define the Bucket, Lambda, IAM Roles, and EventBridge rules in a single configuration file that can be deployed with one command.
