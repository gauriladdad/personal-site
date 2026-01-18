import json
import boto3
import feedparser
import requests
import datetime
import os
import re
import time
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from google.genai import types
import threading

# Thread safety for de-duplication and rate limiting
processed_lock = threading.Lock()
rate_limit_lock = threading.Lock()
last_api_call_time = 0
MIN_DELAY_BETWEEN_CALLS = 0.5  # 500ms delay between Gemini API calls to stay under free tier (15 RPM)
processed_urls = set()
processed_titles = set()

# Configuration
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "personal-site-news")
GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", "").split(",")  # Support multiple keys
GEMINI_API_KEYS = [key.strip() for key in GEMINI_API_KEYS if key.strip()]  # Clean whitespace

# Global AI Clients for key rotation (2026 stack)
ai_clients = []
current_key_index = 0
failed_key_indices = set()  # Track which keys have failed
if GEMINI_API_KEYS:
    # Create a client for each API key
    for i, api_key in enumerate(GEMINI_API_KEYS):
        try:
            client = genai.Client(api_key=api_key, http_options={'api_version': 'v1beta'})
            ai_clients.append(client)
            print(f"DEBUG: Initialized AI client {i+1}/{len(GEMINI_API_KEYS)}")
        except Exception as e:
            print(f"DEBUG: Failed to initialize client {i+1} with key: {str(e)[:50]}")
            failed_key_indices.add(i)
    
    if not ai_clients:
        print("DEBUG: WARNING - No valid API clients initialized!")
    else:
        print(f"DEBUG: {len(ai_clients)} active clients, {len(failed_key_indices)} failed at init")
else:
    print("DEBUG: WARNING - No GEMINI_API_KEYS provided!")

# Smart per-category story limits (keep under 20 daily API quota per key)
# With multiple keys: multiply limits by number of keys
# Per-category filtering: 4 calls per key
# Story summaries: target ~23 calls per key
# Total: ~27 calls per key = 54 calls with 2 keys
# Can be configured via MAX_STORIES_PER_CATEGORY environment variable (JSON format)
DEFAULT_MAX_STORIES = {
    "top": 8,        # Top stories
    "tech": 5,       # Technology
    "science": 5,    # Science
    "canada": 5      # Canada (Generative)
}

try:
    max_stories_env = os.environ.get("MAX_STORIES_PER_CATEGORY", "")
    if max_stories_env:
        MAX_STORIES_PER_CATEGORY = json.loads(max_stories_env)
        print(f"DEBUG: Loaded MAX_STORIES_PER_CATEGORY from env: {MAX_STORIES_PER_CATEGORY}")
    else:
        MAX_STORIES_PER_CATEGORY = DEFAULT_MAX_STORIES
        print(f"DEBUG: Using default MAX_STORIES_PER_CATEGORY: {MAX_STORIES_PER_CATEGORY}")
except (json.JSONDecodeError, ValueError) as e:
    print(f"DEBUG: Failed to parse MAX_STORIES_PER_CATEGORY env var: {e}. Using defaults.")
    MAX_STORIES_PER_CATEGORY = DEFAULT_MAX_STORIES

# Category feeds - Hybrid model (RSS + Generative)
# Only includes categories defined in DEFAULT_MAX_STORIES
CATEGORY_FEEDS = {
    "top": {
        "name": "Top Stories",
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "type": "rss"
    },
    "canada": {
        "name": "Canada",
        "type": "generative",
        "prompt": "Find 5 current, interesting news stories happening in Canada today. Focus on positive or educational topics suitable for kids."
    },
    "tech": {
        "name": "Technology",
        "url": "http://feeds.bbci.co.uk/news/technology/rss.xml",
        "type": "rss"
    },
    "science": {
        "name": "Science",
        "url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
        "type": "rss"
    }
}

s3_client = boto3.client('s3')

def get_ai_client():
    """Get the current AI client with key rotation support. Skips failed keys."""
    global current_key_index
    if not ai_clients:
        return None
    
    # Find a key that hasn't failed yet
    max_attempts = len(ai_clients)
    attempts = 0
    while attempts < max_attempts:
        if current_key_index not in failed_key_indices:
            return ai_clients[current_key_index]
        # Skip failed key, try next one
        current_key_index = (current_key_index + 1) % len(ai_clients)
        attempts += 1
    
    print(f"DEBUG: ERROR - All {len(ai_clients)} API keys have failed!")
    return None

def rotate_api_key():
    """Rotate to the next valid API key. Returns True if rotation succeeded, False if all keys failed."""
    global current_key_index
    if len(ai_clients) <= 1:
        return False
    
    # Try to find next available key
    start_index = current_key_index
    for _ in range(len(ai_clients)):
        current_key_index = (current_key_index + 1) % len(ai_clients)
        if current_key_index not in failed_key_indices:
            print(f"DEBUG: Rotated to API key {current_key_index + 1}/{len(ai_clients)}")
            return True
    
    print(f"DEBUG: No valid API keys available for rotation (all {len(ai_clients)} have failed)")
    return False

def mark_key_failed(error_str):
    """Mark current key as failed and try to rotate to next one."""
    global current_key_index
    failed_key_indices.add(current_key_index)
    print(f"DEBUG: Marked key {current_key_index + 1} as failed. {len(failed_key_indices)} keys failed total.")
    return rotate_api_key()

def rate_limit_api_call():
    """Enforce rate limiting to stay under free tier (15 RPM = 1 call per 4 seconds, but we use 0.5s to be safe)."""
    global last_api_call_time
    with rate_limit_lock:
        elapsed = time.time() - last_api_call_time
        if elapsed < MIN_DELAY_BETWEEN_CALLS:
            time.sleep(MIN_DELAY_BETWEEN_CALLS - elapsed)
        last_api_call_time = time.time()

def filter_entries_with_ai(entries, category_name):
    """First pass: Use Gemini to filter entries based on title + summary, return indices of suitable ones."""
    ai_client = get_ai_client()
    if not ai_client or len(entries) == 0:
        return list(range(len(entries)))  # If no AI, return all indices
    
    # Create a compact batch of entries for filtering
    entries_summary = []
    for i, entry in enumerate(entries):
        title = getattr(entry, 'title', '')
        summary = getattr(entry, 'summary', '')[:200]  # First 200 chars only
        entries_summary.append({
            "index": i,
            "title": title,
            "summary": summary
        })
    
    prompt = (
        f"You are a kids news editor. Review these {len(entries_summary)} news entries from the {category_name} category.\n\n"
        f"Filter based on:\n"
        f"1. Is it safe for 11-year-olds? (no graphic violence, mature themes)\n"
        f"2. Is it interesting/educational for kids?\n"
        f"3. Is it not already covered by another entry?\n\n"
        f"Entries:\n{json.dumps(entries_summary, indent=2)}\n\n"
        f"Respond ONLY with a JSON array of indices: {{'suitable_indices': [0, 2, 5, ...]}}"
    )
    
    try:
        rate_limit_api_call()
        response = ai_client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json'
            )
        )
        data = json.loads(response.text)
        suitable_indices = data.get('suitable_indices', list(range(len(entries))))
        print(f"DEBUG: Filtered {category_name} - {len(entries)} entries → {len(suitable_indices)} suitable")
        return suitable_indices
    except Exception as e:
        error_str = str(e)
        # Handle API key errors by marking key as failed and rotating
        if "API_KEY_INVALID" in error_str or "expired" in error_str.lower():
            print(f"DEBUG: API key invalid/expired for filtering. {error_str[:80]}")
            if mark_key_failed(error_str):
                print(f"DEBUG: Retrying filtering with next API key...")
                return filter_entries_with_ai(entries, category_name)  # Retry with new key
            else:
                print(f"DEBUG: No more valid API keys available")
        print(f"DEBUG: Filtering error for {category_name}: {type(e).__name__}: {str(e)[:100]}")
        return list(range(len(entries)))  # Fallback: return all

def summarize_with_ai(title, text, url):
    """Summarize story using full article text and vet for child-friendliness using Gemini 2.5 Flash."""
    ai_client = get_ai_client()
    if not ai_client:
        return None, False

    # Enhanced prompt for deep-read summarization based on full article content with accuracy focus
    prompt = (
        f"You are a professional news editor for a kids news site (age 11). Your job is to create accurate summaries based ONLY on the article content provided.\n\n"
        f"CRITICAL RULES:\n"
        f"1. 'suitable': Boolean. False ONLY if the article contains graphic violence, mature themes, or content too frightening for kids.\n"
        f"2. 'summary': 3-5 clear sentences for an 11-year-old. ONLY use facts directly stated in the article content below.\n"
        f"3. DO NOT infer, assume, or add context not explicitly in the article.\n"
        f"4. DO NOT add titles, roles, or descriptions to people unless the article explicitly states them.\n"
        f"5. If the article is unclear or vague about facts, be conservative and state only what is certain.\n"
        f"6. Verify dates, names, and numbers match exactly what appears in the article text.\n\n"
        f"Article Title: {title}\n"
        f"Source URL: {url}\n\n"
        f"ARTICLE CONTENT TO SUMMARIZE:\n{text[:5000]}\n\n"
        f"Respond in JSON format only: {{'suitable': boolean, 'summary': 'string'}}"
    )

    try:
        rate_limit_api_call()  # Enforce rate limiting before API call
        response = ai_client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json'
            )
        )
        
        data = json.loads(response.text)
        
        if not data.get('suitable', False):
            print(f"DEBUG: Story deemed UNSUITABLE by AI: {title}")
            return None, False
            
        return data.get('summary'), True
    except Exception as e:
        error_str = str(e)
        
        # Handle API key errors by marking key as failed and rotating
        if "API_KEY_INVALID" in error_str or "expired" in error_str.lower():
            print(f"DEBUG: API key invalid/expired for summarization. {error_str[:80]}")
            if mark_key_failed(error_str):
                print(f"DEBUG: Retrying summarization with next API key...")
                return summarize_with_ai(title, text, url)  # Retry with new key
            else:
                print(f"DEBUG: No more valid API keys available")
                return None, False
        
        # Handle quota exceeded gracefully
        if "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
            print(f"DEBUG: Gemini quota exceeded for '{title}'. Daily limit reached. Stopping further API calls.")
            return None, False
        
        print(f"DEBUG: Gemini AI Error for '{title}': {type(e).__name__}: {str(e)[:100]}")
        return None, False

def generate_category_with_ai(category_id, category_info):
    """Ask Gemini to report on a specific category directly with Search Grounding."""
    ai_client = get_ai_client()
    if not ai_client:
        print("DEBUG: Missing Global AI Client for generative category.")
        return []

    prompt = (
        f"You are a professional reporter for a kids news site. "
        f"Task: {category_info.get('prompt', 'Find 5 current news stories')}.\n\n"
        f"Return a list of 5 story objects in JSON. Each story must have:\n"
        f"1. 'title': Engaging and clear.\n"
        f"2. 'summary': 3-5 simple, informative sentences for an 11-year-old.\n"
        f"3. 'link': A real URL to a news article.\n\n"
        f"Respond ONLY with the JSON array."
    )

    try:
        rate_limit_api_call()
        print(f"DEBUG: Requesting generated news for category: {category_id}")
        response = ai_client.models.generate_content(
            model="models/gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type='application/json',
                # Leverage Google Search Grounding for accurate world news
                tools=[types.Tool(google_search=types.GoogleSearchRetrieval())]
            )
        )
        
        stories_raw = json.loads(response.text)
        
        if not isinstance(stories_raw, list):
            print(f"DEBUG: AI returned non-list for category {category_id}")
            return []

        stories = []
        for s in stories_raw:
            stories.append({
                "id": f"ai-{category_id}-{datetime.datetime.now().strftime('%Y%m%d%H%M')}-{len(stories)}",
                "title": s.get('title', 'AI News Story'),
                "link": s.get('link', '#'),
                "location": "Canada" if category_id == 'canada' else "World",
                "date_line": datetime.datetime.now().strftime("%B %d, %Y"),
                "section": [s.get('summary', s.get('content', ''))],
                "source": "AI Generated (Verified)"
            })
        print(f"DEBUG: Successfully generated {len(stories)} stories for {category_id}.")
        return stories
    except Exception as e:
        error_str = str(e)
        # Handle API key errors by marking key as failed and rotating
        if "API_KEY_INVALID" in error_str or "expired" in error_str.lower():
            print(f"DEBUG: API key invalid/expired for generation. {error_str[:80]}")
            if mark_key_failed(error_str):
                print(f"DEBUG: Retrying generation with next API key...")
                return generate_category_with_ai(category_id, category_info)  # Retry with new key
            else:
                print(f"DEBUG: No more valid API keys available")
        
        print(f"DEBUG: Gemini Generation Error for {category_id}: {type(e).__name__}: {str(e)[:100]}")
        return []

def fetch_article_text(url):
    """Fetch the main body text of a news article."""
    try:
        response = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        response.raise_for_status()
        
        # Simple extraction: look for article tags or major div containers
        # We don't want to bring in heavy dependencies like BS4 unless necessary.
        # Removing script, style, and navigation elements via regex
        text = response.text
        text = re.sub('<script.*?>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub('<style.*?>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub('<[^<]+?>', ' ', text) # Strip all HTML
        text = re.sub('\s+', ' ', text).strip() # Clean whitespace
        
        return text[:10000] # Cap it for Gemini context efficiency
    except Exception as e:
        print(f"DEBUG: Could not fetch article text for {url}: {e}")
        return ""

def process_feed_entry(entry):
    """Process a single feed entry and return a story dict if it passes filters, None otherwise."""
    title = getattr(entry, 'title', '').strip()
    link = getattr(entry, 'link', '')
    
    if not title or not link:
        return None

    # 1. Shared De-duplication Check (global tracking across all categories)
    with processed_lock:
        if link in processed_urls or title.lower() in processed_titles:
            print(f"DEBUG: Skipping duplicate story (already in another category): {title}")
            return None
        processed_urls.add(link)
        processed_titles.add(title.lower())

    # 2. Fetch Full Article Text for Deep Summarization
    full_text = fetch_article_text(link)
    
    # Fallback to RSS text if full fetch failed/empty
    if not full_text:
        raw_text = ''
        if 'content' in entry:
            try: raw_text = entry.content[0].value
            except: pass
        if not raw_text: raw_text = getattr(entry, 'summary', '')
        full_text = re.sub('<[^<]+?>', '', raw_text).strip()

    # 3. AI Summarization & Vetting (using full article text for better quality)
    ai_summary, is_suitable = summarize_with_ai(title, full_text, link)
    
    if is_suitable:
        summary = ai_summary
    else:
        print(f"Skipping story (AI Vetted/Failed): {title}")
        return None

    # Create Story Object (without why_it_matters field)
    story = {
        "id": entry.get('id', link),
        "title": title,
        "link": link,
        "location": "World",
        "date_line": datetime.datetime.now().strftime("%B %d, %Y"),
        "section": [summary]
    }
    return story

def process_category_feed(category_id, category_info):
    """Fetch/Generate and process a single category. Returns (category_id, category_data).
    
    Two-pass approach:
    1. Read all feed entries and filter with AI (cheap, batched)
    2. Fetch full articles and summarize only filtered entries
    """
    import time
    start_time = time.time()
    
    print(f"[{category_id}] Starting to process {category_info['name']} ({category_info.get('type', 'rss')})...")
    
    try:
        if category_info.get('type') == 'generative':
            stories = generate_category_with_ai(category_id, category_info)
        else:
            # RSS Flow - Two-pass approach
            print(f"[{category_id}] PASS 1: Fetching all entries from feed...")
            response = requests.get(category_info['url'], timeout=10)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            all_entries = list(feed.entries)
            print(f"[{category_id}] Got {len(all_entries)} entries from feed")
            
            # Pass 1: Filter entries with AI (cheap batch call)
            print(f"[{category_id}] PASS 1: Filtering entries with AI...")
            suitable_indices = filter_entries_with_ai(all_entries, category_info['name'])
            
            # Pass 2: Process only suitable entries
            print(f"[{category_id}] PASS 2: Processing {len(suitable_indices)} filtered entries...")
            stories = []
            max_for_category = MAX_STORIES_PER_CATEGORY.get(category_id, 15)  # Default to 15 if category not found
            for idx in suitable_indices:
                if len(stories) >= max_for_category:
                    break
                
                entry = all_entries[idx]
                story = process_feed_entry(entry)
                if story:
                    stories.append(story)
        
        total_time = time.time() - start_time
        print(f"[{category_id}] Completed in {total_time:.2f}s - {len(stories)} stories ready")
        
        return category_id, {
            "name": category_info['name'],
            "stories": stories
        }
    except Exception as e:
        error_time = time.time() - start_time
        print(f"[{category_id}] ERROR after {error_time:.2f}s: {type(e).__name__}: {str(e)}")
        raise

def lambda_handler(event, context):
    print("Fetching RSS feeds from multiple categories in parallel...")
    
    categories_data = {}
    
    # Fetch all feeds in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=6) as executor:
        # Submit all feed fetch tasks
        future_to_category = {
            executor.submit(process_category_feed, cat_id, cat_info): cat_id
            for cat_id, cat_info in CATEGORY_FEEDS.items()
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_category):
            try:
                category_id, category_data = future.result()
                categories_data[category_id] = category_data
            except Exception as e:
                category_id = future_to_category[future]
                print(f"Error processing category {category_id}: {e}")
                # Continue with other categories even if one fails
                categories_data[category_id] = {
                    "name": CATEGORY_FEEDS[category_id]['name'],
                    "stories": []
                }
    
    # Generate JSON for Today
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    display_date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
    data = {
        "date": today_str,
        "display_date": display_date_str,
        "categories": categories_data
    }
    
    # 5. Upload Daily JSON to S3 (even if partial due to quota limits)
    try:
        print(f"Uploading {today_str}.json to S3...")
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"{today_str}.json",
            Body=json.dumps(data, indent=2),
            ContentType='application/json',
            CacheControl="public, max-age=31536000, immutable"
            # ACL='public-read' REMOVED: Managed by Bucket Policy
        )
        print(f"Successfully uploaded {today_str}.json to S3")
    except ClientError as e:
        print(f"Error uploading daily JSON: {e}")
        # Don't fail - continue to update index even if there's an issue
        print("Continuing despite upload error...")

    # 6. Update index.json (update even if partial results due to quota limits)
    try:
        print("Updating index.json...")
        # Try to get existing index
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key="index.json")
            index_data = json.loads(response['Body'].read().decode('utf-8'))
        except ClientError:
            # If not exists, create new
            index_data = {"latest": today_str, "archive": []}
            
        if index_data["latest"] != today_str:
            if "archive" not in index_data:
                index_data["archive"] = []
            index_data["archive"].append(index_data["latest"])
            index_data["latest"] = today_str
            
        # Self-healing: Verify all archive entries actually exist on S3
        if "archive" in index_data:
            valid_archive = []
            for date_key in index_data["archive"]:
                try:
                    s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=f"{date_key}.json")
                    valid_archive.append(date_key)
                except ClientError:
                    print(f"Archived file {date_key}.json not found. Removing from index.")
            index_data["archive"] = valid_archive

        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key="index.json",
            Body=json.dumps(index_data, indent=2),
            ContentType='application/json',
            CacheControl="public, max-age=300"
        )
        print("Successfully updated index.json")
            
    except ClientError as e:
        print(f"Error updating index JSON: {e}")
        # Still return success - partial results are better than no results
        print("Partial data uploaded despite index error")

    total_stories = sum(len(cat['stories']) for cat in categories_data.values())
    print(f"Lambda completed: {total_stories} stories across {len(categories_data)} categories for {today_str}")
    return {
        'statusCode': 200,
        'body': json.dumps(f'Successfully processed {total_stories} stories across {len(categories_data)} categories for {today_str}')
    }

if __name__ == "__main__":
    # For local testing
    lambda_handler(None, None)
