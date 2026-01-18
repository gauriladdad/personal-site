# Kids News 📰🤖

A premium, minimalist news site designed specifically for kids. It features a hybrid AI pipeline that combines reliable reporting from world-class sources with smart, kid-friendly AI summaries.

Live at: [news.gattani.ca](https://news.gattani.ca)

## Core Features

- **Intelligent Two-Pass AI Pipeline** (optimized for free tier):
  - **Pass 1 - Smart Filtering**: Reads ALL feed entries and uses Gemini to filter suitable stories (cheap batch call)
  - **Pass 2 - Deep Summarization**: Fetches full article text ONLY for filtered stories and creates comprehensive summaries
  - **Rate Limiting**: Built-in 500ms delays between API calls to stay safely under Gemini free tier (15 RPM)
- **Full-Article Summarization**: Reads complete article content instead of shallow RSS snippets for better context and accuracy
- **AI-Driven Vetting**: All stories evaluated for safety, child-friendliness, and factual accuracy with strict no-inference rules
- **Smart De-duplication**: Shared tracking across categories ensures the same story never appears twice, even in the "All" view
- **Per-Category Coverage**:
  - Top Stories: 20 stories
  - Technology & Science: 15 stories each
  - Health: 12 stories
  - Politics: 10 stories (conservative curation)
  - Canada: 8 AI-generated stories
- **Modern UI/UX**:
  - **Clean Category Navigation**: Integrated pills and headers for focused browsing
  - **Theme Switcher**: Light and Dark modes with persistent storage
  - **Responsive Design**: Works seamlessly on mobile, tablet, and desktop
- **Optimized for Growth**:
  - **SEO & Social**: Full Open Graph, Twitter Card, and Meta tag support
  - **Google Analytics**: Integrated tracking for user engagement insights

## Technology Stack

- **Frontend**: [Astro](https://astro.build/) (v4+) for zero-JS performance and static optimization
- **Backend**: AWS Lambda (Python 3.12) with intelligent batching & rate limiting
- **Storage**: AWS S3 for hosting JSON news data (CloudFront CDN compatible)
- **AI Engine**: Google Gemini 2.5 Flash (free tier friendly)
- **Feeds**: BBC News RSS (6 categories)

## Lambda Performance & API Quota

- **Runtime**: ~2-3 minutes per execution
- **Daily API Quota**: 20 Gemini API calls per day (free tier limit)
  - 6 calls for per-category filtering
  - ~12-14 calls for story summarization
  - **Total: ~18-20 calls** ✅ Fits within free tier
- **Stories Generated**: ~50-60 per day (after filtering & deduplication)
- **Graceful Degradation**: If quota is exceeded mid-run, Lambda publishes partial results to S3 instead of failing completely

**⚠️ Important:** The Gemini free tier has a **hard limit of 20 API calls per day**. This is separate from rate limiting. Once this quota is reached, the Lambda will gracefully populate S3 with whatever stories were successfully processed and continue the next day.

## Getting Started

1. **Install Dependencies**:

   ```bash
   npm install
   ```

2. **Run Development Server**:

   ```bash
   npm run dev
   ```

3. **Backend Setup**:
   - Lambda function is in `/backend/lambda_function.py`
   - Run `build_lambda.sh` to package dependencies
   - Set AWS Lambda environment variables (see below)

## AWS Lambda Environment Variables

Configure these in your AWS Lambda function settings:

```
GEMINI_API_KEY          → Your Google Gemini API key (get from https://aistudio.google.com/)
S3_BUCKET_NAME          → Your S3 bucket name (e.g., "personal-site-news")
```

**Lambda Configuration Recommendations:**

- **Memory**: 512 MB (sufficient for 2-3 minute runtime)
- **Timeout**: 300 seconds (5 minutes) - provides safety margin
- **Trigger**: EventBridge rule set to run daily (e.g., `cron(0 7 * * ? *)` for 7 AM UTC)

## Deployment

- **Frontend**: Deployed on **Cloudflare Pages**
  - Build command: `npm run build`
  - Output directory: `dist`
  - Auto-deploys on push to main branch
- **Backend**: Deployed on **AWS Lambda**
  - Zip the `/backend` folder after running `build_lambda.sh`
  - Upload to Lambda or use AWS CLI
  - EventBridge trigger for daily execution
- **Backend**: Deployed on **AWS Lambda** with an EventBridge trigger for daily updates.
- **Content**: Served via **AWS S3** (public bucket or CloudFront).
