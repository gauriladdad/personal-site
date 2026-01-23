Kids News 📰
============

A calm, kid-friendly daily news site that helps children read real news at the right level — without ads, doomscrolling, or parents hovering.

**Live:** [https://news.gattani.ca](https://news.gattani.ca)

What This Is
------------

Kids News is a **static site + serverless pipeline** that:

*   Reads real journalism from trusted sources
    
*   Uses AI **only** to simplify, summarize, and classify
    
*   Publishes once per day as static JSON
    
*   Costs ~$0 to run (free tiers only)
    

There are **no user accounts**, **no tracking**, and **no personalization**.

Core Features
-------------

### 🧠 AI-Assisted Editorial Pipeline

*   Reads full articles (not just RSS snippets)
    
*   Produces **fact-only summaries** (3–5 sentences)
    
*   Assigns:
    
    *   **Age buckets**: 7–9, 10–12, 13–15
        
    *   **Safety flags**: science, technology, environment, politics, world-news, crime
        
*   Strict rule: _If unsure → exclude_
    

### 👶 Age-Aware Reading

*   Kids can switch age levels instantly
    
*   Parents don’t need to pre-configure anything
    
*   Stories unsuitable for an age simply don’t appear
    

### 🗂️ Simple Navigation

*   Category pills (World, Canada, Science, Tech)
    
*   Archive view by date
    
*   No infinite scroll, no autoplay, no dark patterns
    

### ⚡ Fast & Free

*   Fully static frontend (Astro + Cloudflare Pages)
    
*   News delivered as static JSON from S3
    
*   No server running 24/7
    

Tech Stack
----------

LayerTechnologyFrontendAstro (static build)HostingCloudflare PagesDataAWS S3 (JSON files)BackendAWS Lambda (Python)SchedulerAWS EventBridgeAIGoogle Gemini 2.5 FlashFeedsBBC World News, ScienceDaily, Government of Canada (Atom)

How It Works (High Level)
-------------------------

1.  **Once per day**, Lambda runs
    
2.  Fetches RSS / Atom feeds
    
3.  Deduplicates stories globally
    
4.  Uses Gemini to:
    
    *   Decide if a story is kid-safe
        
    *   Assign age bucket + flags
        
    *   Generate summary
        
5.  Writes:
    
    *   YYYY-MM-DD.json (daily news)
        
    *   index.json (latest + archive)
        
6.  Frontend fetches JSON directly from S3
    

No rebuild is required to publish news.

Environment Variables (Lambda)
------------------------------

Plain textANTLR4BashCC#CSSCoffeeScriptCMakeDartDjangoDockerEJSErlangGitGoGraphQLGroovyHTMLJavaJavaScriptJSONJSXKotlinLaTeXLessLuaMakefileMarkdownMATLABMarkupObjective-CPerlPHPPowerShell.propertiesProtocol BuffersPythonRRubySass (Sass)Sass (Scss)SchemeSQLShellSwiftSVGTSXTypeScriptWebAssemblyYAMLXML`   S3_BUCKET_NAME=personal-site-news  GEMINI_API_KEYS=key1,key2,key3   `

> Multiple Gemini keys are rotated automatically to stay within free-tier quotas.

Deployment
----------

### Frontend

*   Platform: Cloudflare Pages
    
*   Build: npm run build
    
*   Output: /dist
    
*   PUBLIC\_S3\_BUCKET\_URL=https://.s3.amazonaws.com
    

### Backend

*   Package with build\_lambda.sh
    
*   Upload zip to AWS Lambda
    
*   Memory: 512 MB
    
*   Timeout: 15 minutes
    
*   Trigger: EventBridge (daily)
    

Philosophy
----------

*   **No breaking news**
    
*   **No push notifications**
    
*   **No outrage optimization**
    
*   **No hallucinated facts**
    

This is intentionally boring software — so kids can focus on learning, not reacting.

Status
------

This is a **personal project**, actively iterated in public.

Feedback welcome.
