import json
import boto3
import feedparser
import requests
import datetime
import os
import re
import time
import threading
from botocore.exceptions import ClientError
from google import genai
from google.genai import types

# -------------------------
# Globals / Config
# -------------------------

processed_lock = threading.Lock()
rate_limit_lock = threading.Lock()
last_api_call_time = 0
MIN_DELAY_BETWEEN_CALLS = 13

processed_urls = set()
processed_titles = set()

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "personal-site-news")

GEMINI_API_KEYS = [
    k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()
]

DEFAULT_MAX_STORIES = {
    "world": 6,
    "canada": 6,
    "tech": 6,
    "science": 6,
}

MAX_STORIES_PER_CATEGORY = DEFAULT_MAX_STORIES

CATEGORY_FEEDS = {
    "world": {
        "name": "World News",
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "type": "rss"
    },
    "canada": {
        "name": "Top Stories in Canada",
        "url": "https://api.io.canada.ca/io-server/gc/news/en/v2"
               "?audience=children"
               "&sort=publishedDate"
               "&orderBy=desc"
               "&pick=100"
               "&format=atom",
        "type": "rss"
    },
    "tech": {
        "name": "Technology",
        "url": "https://www.sciencedaily.com/rss/top/technology.xml",
        "type": "rss"
    },
    "science": {
        "name": "Science",
        "url": "https://www.sciencedaily.com/rss/top/science.xml",
        "type": "rss"
    },
}

s3_client = boto3.client("s3")

# -------------------------
# Gemini Client Handling
# -------------------------

ai_clients = []
failed_key_indices = set()
current_key_index = 0

for i, key in enumerate(GEMINI_API_KEYS):
    try:
        ai_clients.append(genai.Client(api_key=key, http_options={"api_version": "v1beta"}))
    except Exception:
        failed_key_indices.add(i)

def get_ai_client():
    global current_key_index
    for _ in range(len(ai_clients)):
        if current_key_index not in failed_key_indices:
            return ai_clients[current_key_index]
        current_key_index = (current_key_index + 1) % len(ai_clients)
    return None

def mark_current_key_failed():
    global current_key_index
    failed_key_indices.add(current_key_index)
    print(f"DEBUG: Marked Gemini key #{current_key_index} as exhausted")

    # Move to next key
    current_key_index = (current_key_index + 1) % len(ai_clients)

def extract_link(entry):
    # RSS feeds
    if hasattr(entry, "link") and isinstance(entry.link, str):
        return entry.link.strip()

    # Atom feeds (like api.io.canada.ca)
    if hasattr(entry, "links") and entry.links:
        for l in entry.links:
            href = l.get("href")
            if href:
                return href.strip()

    return ""

def rate_limit_api_call():
    global last_api_call_time
    with rate_limit_lock:
        elapsed = time.time() - last_api_call_time
        if elapsed < MIN_DELAY_BETWEEN_CALLS:
            time.sleep(MIN_DELAY_BETWEEN_CALLS - elapsed)
        last_api_call_time = time.time()

# -------------------------
# AI Calls
# -------------------------

def summarize_batch_with_ai(articles):
    client = get_ai_client()
    if not client or not articles:
        return {}

    prompt = (
        "You are an editor for a kids news site.\n\n"

        "CONTENT SAFETY:\n"
        "If the article discusses war, terrorism, graphic violence, sexual content, "
        "or adult political conflict, mark it as 'exclude' for ages under 13.\n\n"

        "For EACH article:\n"
        "- suitable: boolean\n"
        "- ageBucket: '7-9', '10-12', '13-15', or 'exclude'\n"
        "- flags: an array of zero or more labels from this fixed list ONLY:\n"
        "  ['world-news', 'politics', 'science', 'technology', 'environment', 'crime']\n"
        "- summary: 3–5 factual sentences\n\n"

        "FLAG RULES:\n"
        "- Use 'world-news' for international events or global affairs\n"
        "- Use 'politics' for government, elections, or public policy\n"
        "- Use 'crime' ONLY if non-graphic and suitable for teens\n"
        "- Use 'science' or 'technology' when the focus is research or innovation\n"
        "- Use 'environment' for climate, wildlife, or nature-related stories\n"
        "- If no flag clearly applies, return an empty array\n\n"

        "GENERAL RULES:\n"
        "- Use only facts from the article\n"
        "- Do not add opinions or advice\n"
        "- If unsure, choose 'exclude'\n\n"

        "Return ONLY valid JSON in this format:\n"
        "[{id, suitable, ageBucket, flags, summary}]\n\n"

        f"ARTICLES:\n{json.dumps(articles, separators=(',', ':'))}"
    )


    try:
        rate_limit_api_call()
        resp = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        results = json.loads(resp.text)
        return {r["id"]: r for r in results if isinstance(r, dict)}
    except Exception as e:
        error_str = str(e)

        if "RESOURCE_EXHAUSTED" in error_str:
            print("DEBUG: Gemini quota exhausted for current key")

            mark_current_key_failed()

            # Try again with the next key (if any remain)
            if len(failed_key_indices) < len(ai_clients):
                print("DEBUG: Retrying batch with next Gemini key")
                return summarize_batch_with_ai(articles)
            
            print("DEBUG: All Gemini keys exhausted")
            return {"__all_keys_exhausted__": True}

        print(f"DEBUG: Batch summarization failed: {error_str[:100]}")
        return {}

def filter_entries_with_ai(entries, category_name):
    client = get_ai_client()
    if not client or not entries:
        return list(range(len(entries)))

    payload = [
        {
            "index": i,
            "title": getattr(e, "title", ""),
            "summary": getattr(e, "summary", "")[:200]
        }
        for i, e in enumerate(entries)
    ]

    prompt = (
        f"Filter kid-safe, interesting items from {category_name}.\n\n"
        f"Return JSON: {{\"suitable_indices\": [..]}}\n\n"
        f"{json.dumps(payload, separators=(',', ':'))}"
    )

    try:
        rate_limit_api_call()
        resp = client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(resp.text).get("suitable_indices", [])
    except Exception as e:
        if "RESOURCE_EXHAUSTED" in str(e):
            print("DEBUG: Gemini quota exhausted during filtering")
            mark_current_key_failed()

            if len(failed_key_indices) < len(ai_clients):
                print("DEBUG: Retrying filtering with next Gemini key")
                return filter_entries_with_ai(entries, category_name)

            print("DEBUG: All Gemini keys exhausted during filtering")
            return list(range(len(entries)))

        return list(range(len(entries)))

# -------------------------
# Helpers
# -------------------------

def fetch_article_text(url):
    try:
        r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        text = re.sub("<[^>]+>", " ", r.text)
        return re.sub(r"\s+", " ", text).strip()[:5000]
    except Exception:
        return ""

def process_feed_entry(entry):
    title = getattr(entry, "title", "").strip()
    link = extract_link(entry)

    if not title or not link:
        return None

    with processed_lock:
        if link in processed_urls or title.lower() in processed_titles:
            return None
        processed_urls.add(link)
        processed_titles.add(title.lower())

    text = fetch_article_text(link)
    if not text or len(text) < 200:
        return None

    return {
        "id": entry.get("id", link),
        "title": title,
        "url": link,
        "text": text
    }

def build_story_from_ai(article, ai):
    return {
        "id": article["id"],
        "title": article["title"],
        "link": article["url"],
        "date_line": datetime.datetime.now().strftime("%B %d, %Y"),
        "section": [ai["summary"]],
        "ageBucket": ai["ageBucket"],
        "flags": ai.get("flags", [])
    }

# -------------------------
# Category Processing
# -------------------------

def process_category_feed(category_id, category_info):
    if category_info["type"] == "generative":
        return category_id, {
            "name": category_info["name"],
            "stories": []
        }

    feed = feedparser.parse(requests.get(category_info["url"], timeout=10).content)
    entries = feed.entries

    suitable_indices = filter_entries_with_ai(entries, category_info["name"])

    stories = []
    batch = []
    BATCH_SIZE = 2
    MAX_STORIES = MAX_STORIES_PER_CATEGORY.get(category_id, 10)

    for idx in suitable_indices:
        if len(stories) >= MAX_STORIES:
            break

        article = process_feed_entry(entries[idx])
        if not article:
            continue

        batch.append(article)

        if len(batch) == BATCH_SIZE:
            results = summarize_batch_with_ai(batch)

            if "__all_keys_exhausted__" in results:
                print("DEBUG: All Gemini projects exhausted — stopping category")
                return category_id, {
                    "name": category_info["name"],
                    "stories": stories
                }

            for a in batch:
                ai = results.get(a["id"])
                if ai and ai.get("suitable") and ai.get("ageBucket") != "exclude":
                    stories.append(build_story_from_ai(a, ai))
            batch = []

    if batch:
        results = summarize_batch_with_ai(batch)

        if "__all_keys_exhausted__" in results:
            print("DEBUG: Quota exhausted during final batch — stopping")
            return category_id, {
                "name": category_info["name"],
                "stories": stories
            }

        for a in batch:
            ai = results.get(a["id"])
            if ai and ai.get("suitable") and ai.get("ageBucket") != "exclude":
                stories.append(build_story_from_ai(a, ai))

    return category_id, {
        "name": category_info["name"],
        "stories": stories
    }

# -------------------------
# Lambda Entry
# -------------------------

def lambda_handler(event, context):
    categories = {}

    for cid, info in CATEGORY_FEEDS.items():
        cid, data = process_category_feed(cid, info)
        categories[cid] = data

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    payload = {
        "date": today,
        "categories": categories
    }

    # 1. Upload daily JSON
    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=f"{today}.json",
        Body=json.dumps(payload, indent=2),
        ContentType="application/json"
    )

    # 2. Update index.json
    try:
        response = s3_client.get_object(
            Bucket=S3_BUCKET_NAME,
            Key="index.json"
        )
        index_data = json.loads(response["Body"].read())
    except ClientError:
        index_data = {
            "latest": None,
            "archive": []
        }

    if index_data.get("latest") != today:
        if index_data.get("latest"):
            index_data.setdefault("archive", []).append(index_data["latest"])
        index_data["latest"] = today

    index_data["archive"] = sorted(set(index_data.get("archive", [])))

    s3_client.put_object(
        Bucket=S3_BUCKET_NAME,
        Key="index.json",
        Body=json.dumps(index_data, indent=2),
        ContentType="application/json",
        CacheControl="public, max-age=300"
    )

    return {"statusCode": 200, "body": "OK"}


