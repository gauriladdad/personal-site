import json
import boto3
import feedparser
import requests
import datetime
import os
import re
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "personal-site-news")
MIN_READABILITY_SCORE = 50.0
MAX_STORIES_PER_CATEGORY = 5

# Category feeds - Using feeds that work reliably with Lambda
CATEGORY_FEEDS = {
    "top": {
        "name": "Top Stories",
        "url": "http://feeds.bbci.co.uk/news/rss.xml"
    },
    "education": {
        "name": "Education",
        "url": "https://feeds.bbci.co.uk/news/education/rss.xml"
    },
    "health": {
        "name": "Health",
        "url": "https://feeds.bbci.co.uk/news/health/rss.xml"
    },
    "politics": {
        "name": "Politics",
        "url": "http://feeds.bbci.co.uk/news/politics/rss.xml"
    },
    "science": {
        "name": "Science",
        "url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
    },
    "tech": {
        "name": "Technology",
        "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"
    }
}

s3_client = boto3.client('s3')

def estimate_syllables(word):
    word = word.lower()
    count = 0
    vowels = "aeiouy"
    if word and word[0] in vowels:
        count += 1
    for index in range(1, len(word)):
        if word[index] in vowels and word[index - 1] not in vowels:
            count += 1
    if word.endswith("e"):
        count -= 1
    if count == 0:
        count += 1
    return count

def calculate_flesch_reading_ease(text):
    if not text: return 0
    sentences = max(1, text.count('.') + text.count('!') + text.count('?'))
    words = re.findall(r'\w+', text)
    num_words = max(1, len(words))
    num_syllables = sum(estimate_syllables(w) for w in words)
    
    # Flesch Reading Ease Formula
    score = 206.835 - (1.015 * (num_words / sentences)) - (84.6 * (num_syllables / num_words))
    return score

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
    
    # Truncate to roughly 4 sentences to avoid being too long
    sentences = clean_text.split('. ')
    if len(sentences) > 4:
        clean_summary = '. '.join(sentences[:4]) + '.'
    else:
        clean_summary = clean_text
    
    # 2. Smart Filter: Keyword Safety Check
    unsafe_keywords = ['murder', 'kill', 'death', 'crime', 'assault', 'terror', 'drug', 'sex', 'violent', 'war', 'gun']
    if any(keyword in title.lower() or keyword in clean_summary.lower() for keyword in unsafe_keywords):
        print(f"Skipping unsafe story: {title}")
        return None
        
    # 3. Smart Filter: Readability Check
    readability = calculate_flesch_reading_ease(clean_summary)
    if readability < MIN_READABILITY_SCORE:
        print(f"Skipping complex story (Score: {readability}): {title}")
        return None
    
    # Create Story Object
    story = {
        "id": entry.get('id', link),
        "title": title,
        "link": link,
        "location": "World",  # Placeholder
        "date_line": datetime.datetime.now().strftime("%B %d, %Y"),
        "section": [clean_summary],
        "why_it_matters": "News from around the world."
    }
    return story

def process_category_feed(category_id, category_info):
    """Fetch and process a single category feed. Returns (category_id, category_data)."""
    import time
    start_time = time.time()
    
    print(f"[{category_id}] Starting to fetch {category_info['name']}...")
    
    try:
        # Fetch with explicit timeout using requests
        print(f"[{category_id}] Requesting URL with 10s timeout...")
        response = requests.get(category_info['url'], timeout=10)
        response.raise_for_status()
        
        fetch_time = time.time() - start_time
        print(f"[{category_id}] Downloaded in {fetch_time:.2f}s, parsing feed...")
        
        # Parse the downloaded content
        feed = feedparser.parse(response.content)
        parse_time = time.time() - start_time
        print(f"[{category_id}] Parsed in {parse_time:.2f}s, found {len(feed.entries)} entries")
        
        stories = []
        for entry in feed.entries:
            if len(stories) >= MAX_STORIES_PER_CATEGORY:
                break
            
            story = process_feed_entry(entry)
            if story:
                stories.append(story)
        
        total_time = time.time() - start_time
        print(f"[{category_id}] Completed in {total_time:.2f}s - {len(stories)} stories passed filters")
        
        return category_id, {
            "name": category_info['name'],
            "stories": stories
        }
    except requests.Timeout:
        error_time = time.time() - start_time
        print(f"[{category_id}] TIMEOUT after {error_time:.2f}s - feed took too long to respond")
        raise
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
