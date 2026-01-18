import json
import boto3
import feedparser
import requests
import datetime
import os
import re
from botocore.exceptions import ClientError

# Configuration
# You can set these as Environment Variables in the Lambda configuration
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "personal-site-news")
RSS_FEED_URL = os.environ.get("RSS_FEED_URL", "https://www.cbsnews.com/latest/rss/main")
MIN_READABILITY_SCORE = 50.0 # Adjusted for our simple heuristic
MAX_STORIES = 5

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

def lambda_handler(event, context):
    print("Fetching RSS feed...")
    feed = feedparser.parse(RSS_FEED_URL)
    
    stories = []
    
    for entry in feed.entries:
        if len(stories) >= MAX_STORIES:
            break
            
        title = entry.title
        summary = getattr(entry, 'summary', '')
        link = entry.link
        
        # 1. Clean and Prepare Text
        # Basic cleaning (removing HTML tags if any - simple approach)
        clean_summary = summary.replace('<p>', '').replace('</p>', '').strip()
        
        # 2. Smart Filter: Keyword Safety Check
        # specific keywords to avoid for a "kid friendly" site
        unsafe_keywords = ['murder', 'kill', 'death', 'crime', 'assault', 'terror', 'drug', 'sex', 'violent', 'war', 'gun']
        if any(keyword in title.lower() or keyword in clean_summary.lower() for keyword in unsafe_keywords):
            print(f"Skipping unsafe story: {title}")
            continue
            
        # 3. Smart Filter: Readability Check
        # Using our manual function
        readability = calculate_flesch_reading_ease(clean_summary)
        if readability < MIN_READABILITY_SCORE:
            print(f"Skipping complex story (Score: {readability}): {title}")
            continue
            
        # Create Story Object
        # Since we don't have AI to generate "Why it matters" or split into sections, 
        # we will use the summary for section and a placeholder or simply omit 'why_it_matters' if the frontend handles it.
        # However, to match the existing JSON structure, we will format it.
        
        story = {
            "id": entry.get('id', link),
            "title": title,
            "link": link,
            "location": "World", # Placeholder as RSS might not have location
            "date_line": datetime.datetime.now().strftime("%B %d, %Y"),
            "section": [clean_summary], # List of paragraphs
            "why_it_matters": "News from around the world." # Generic fallback since we lack AI
        }
        stories.append(story)

    # 4. Generate JSON for Today
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    display_date_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
    data = {
        "date": today_str,
        "display_date": display_date_str,
        "stories": stories
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

    return {
        'statusCode': 200,
        'body': json.dumps(f'Successfully processed {len(stories)} stories for {today_str}')
    }

if __name__ == "__main__":
    # For local testing
    lambda_handler(None, None)
