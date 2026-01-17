# System Architecture

## Overview
This document outlines the "Serverless Static" architecture used to host the Personal News Site with zero running costs (AWS Free Tier). It moves the site away from local data files to a cloud-hosted, automated pipeline.

## Current Architecture (Phase 1: S3 & Lambda)

### 1. Data Storage (AWS S3)
*   **Service**: Amazon Simple Storage Service (S3).
*   **Role**: Acts as the "Database" and "API" for the frontend.
*   **Data Format**: Static JSON files.
    *   `index.json`: Manifest of available dates.
    *   `YYYY-MM-DD.json`: Daily news content.
*   **Access**: Public Read access (via Bucket Policy/ACL) allows the frontend to fetch JSON directly via HTTP.
*   **Cost**: Free Tier (First 5GB storage, 20k GET requests).

### 2. Frontend (Astro SPA)
*   **Host**: Cloudflare Pages.
*   **Mechanism**: Client-Side Fetching.
*   **Flow**:
    1.  User visits `news.gattani.ca`.
    2.  Browser loads the static HTML/JS shell.
    3.  JavaScript fetches `S3_BUCKET_URL/index.json` to find the latest date.
    4.  JavaScript fetches `S3_BUCKET_URL/{date}.json` to render stories.
*   **Advantage**: separating data from the build process means we don't need to rebuild the site to publish news.

### 3. Automation (AWS Lambda + EventBridge)
*   **Service**: AWS Lambda (Python 3.12).
*   **Role**: ETL (Extract, Transform, Load) worker.
*   **Changes**:
    *   **Extract**: Fetches public RSS feeds (e.g., CBS News).
    *   **Transform**: Filters content for "kid-safety" using Python libraries (`textstat`, keyword lists).
    *   **Load**: Uploads the resulting JSON to the S3 Bucket.
*   **Trigger**: AWS EventBridge Scheduler runs the Lambda function **once a week** (e.g., every Monday at noon).

## Future Roadmap (Phase 2: Database & IaC)

The following improvements are planned to scale the system and introduce professional Cloud Engineering practices.

### 1. Database (DynamoDB)
*   **Why**: Replacing S3 JSON files with a real database allows for:
    *   Querying by category, date range, or keywords.
    *   Storing user interactions (likes/bookmarks) in the future.
*   **Design**:
    *   **Table**: `NewsStories` (Partition Key: `Date`, Sort Key: `StoryId`).
    *   **API**: Requires an **API Gateway** in front of Lambda to query DynamoDB, as browsers cannot query DynamoDB directly securely.

### 2. Infrastructure as Code (IaC)
*   **Why**: Clicking through the AWS Console is prone to error and hard to replicate.
*   **Tool**: **Terraform** or **AWS SAM**.
*   **Goal**: Define the Bucket, Lambda, IAM Roles, and EventBridge rules in a single configuration file that can be deployed with one command.
