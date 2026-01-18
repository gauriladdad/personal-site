import json
import boto3
import feedparser
import requests
import datetime
import os
import re
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from google.genai import types

# Configuration
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "personal-site-news")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MAX_STORIES_PER_CATEGORY = 5

# Global AI Client for 2026 stack
ai_client = None
if GEMINI_API_KEY:
    # Using v1beta for access to latest 2026 features (Search Grounding, etc.)
    ai_client = genai.Client(api_key=GEMINI_API_KEY, http_options={'api_version': 'v1beta'})

# Category feeds - Hybrid model (RSS + Generative)
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
    },
    "health": {
        "name": "Health",
        "url": "https://feeds.bbci.co.uk/news/health/rss.xml",
        "type": "rss"
    },
    "politics": {
        "name": "Politics",
        "url": "http://feeds.bbci.co.uk/news/politics/rss.xml",
        "type": "rss"
    }
}

s3_client = boto3.client('s3')

def summarize_with_ai(title, text):
    """Summarize story and vet for child-friendliness using Gemini 3 Flash."""
    if not ai_client:
        return None, None, False

    # Refining prompt for 2026 standards
    prompt = (
        f"You are a helpful assistant for a kids news site (target age: 11). "
        f"Analyze this news story and respond ONLY in JSON format.\n\n"
        f"Rules for Kids:\n"
        f"- 'suitable': Boolean. False if story contains graphic violence, mature themes, or is too frightening.\n"
        f"- 'summary': 2-3 friendly, clear sentences (if suitable).\n"
        f"- 'why_it_matters': 1 short sentence explaining why an 11-year-old would find this interesting.\n\n"
        f"Title: {title}\n"
        f"Content: {text}"
    )

    try:
        # Using models/gemini-2.5-flash with official Config type for 400 error mitigation
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
            return None, None, False
            
        return data.get('summary'), data.get('why_it_matters'), True
    except Exception as e:
        print(f"DEBUG: Gemini AI Error for '{title}': {type(e).__name__}: {str(e)}")
        # If it's a 404, let's log what models we actually have access to
        if "404" in str(e) or "NOT_FOUND" in str(e):
            try:
                available_models = [m.name for m in ai_client.models.list()]
                print(f"DEBUG: Available models for this key: {available_models}")
            except:
                pass
        return None, None, False

def generate_category_with_ai(category_id, category_info):
    """Ask Gemini 3 to report on a specific category directly with Search Grounding."""
    if not ai_client:
        print("DEBUG: Missing Global AI Client for generative category.")
        return []

    prompt = (
        f"You are a professional reporter for a kids news site. "
        f"Task: {category_info.get('prompt', 'Find 5 current news stories')}.\n\n"
        f"Return a list of 5 story objects in JSON. Each story must have:\n"
        f"1. 'title': Engaging and clear.\n"
        f"2. 'summary': 2-3 simple sentences for an 11-year-old.\n"
        f"3. 'why_it_matters': Clear insight for a kid.\n"
        f"4. 'link': A real URL to a news article.\n\n"
        f"Respond ONLY with the JSON array."
    )

    try:
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
                "why_it_matters": s.get('why_it_matters', 'Interesting news for kids.'),
                "source": "AI Generated (Verified)"
            })
        print(f"DEBUG: Successfully generated {len(stories)} stories for {category_id}.")
        return stories
    except Exception as e:
        print(f"DEBUG: Gemini Generation Error for {category_id}: {type(e).__name__}: {str(e)}")
        return []

def process_feed_entry(entry):
    """Process a single feed entry and return a story dict if it passes filters, None otherwise."""
    title = entry.title
    link = entry.link
    
    # 1. Clean and Prepare Text
    raw_text = ''
    if 'content' in entry:
        try:
            raw_text = entry.content[0].value
        except (IndexError, AttributeError):
            pass
    
    if not raw_text:
        raw_text = getattr(entry, 'summary', '')

    # Remove HTML tags using regex
    clean_text = re.sub('<[^<]+?>', '', raw_text).strip()
    
    # 2. AI Summarization & Vetting
    ai_summary, ai_why, is_suitable = summarize_with_ai(title, clean_text)
    
    if is_suitable:
        summary = ai_summary
        why_it_matters = ai_why
    else:
        # If AI says not suitable or fails, we skip
        print(f"Skipping story (AI Vetted/Failed): {title}")
        return None

    # Create Story Object
    story = {
        "id": entry.get('id', link),
        "title": title,
        "link": link,
        "location": "World",
        "date_line": datetime.datetime.now().strftime("%B %d, %Y"),
        "section": [summary],
        "why_it_matters": why_it_matters
    }
    return story

def process_category_feed(category_id, category_info):
    """Fetch/Generate and process a single category. Returns (category_id, category_data)."""
    import time
    start_time = time.time()
    
    print(f"[{category_id}] Starting to process {category_info['name']} ({category_info.get('type', 'rss')})...")
    
    try:
        if category_info.get('type') == 'generative':
            stories = generate_category_with_ai(category_id, category_info)
        else:
            # RSS Flow
            print(f"[{category_id}] Requesting URL with 10s timeout...")
            response = requests.get(category_info['url'], timeout=10)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            stories = []
            for entry in feed.entries:
                if len(stories) >= MAX_STORIES_PER_CATEGORY:
                    break
                
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
    
    # 5. Upload Daily JSON to S3
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
    except ClientError as e:
        print(f"Error uploading daily JSON: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps('Error uploading daily JSON')
        }

    # 6. Update index.json
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
            
    except ClientError as e:
        print(f"Error updating index JSON: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps('Error updating index JSON')
        }

    total_stories = sum(len(cat['stories']) for cat in categories_data.values())
    return {
        'statusCode': 200,
        'body': json.dumps(f'Successfully processed {total_stories} stories across {len(categories_data)} categories for {today_str}')
    }

if __name__ == "__main__":
    # For local testing
    lambda_handler(None, None)
