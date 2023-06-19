from pygelbooru import Gelbooru
from time import sleep, mktime
import requests, json, asyncio
from datetime import datetime

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S%z"
ALL_POSTS_PATH = "all_posts.json"
SENT_POSTS_PATH = "sent_posts.json"
LIMIT = 100
REFRESH_DELAY = 60 * 60 # 1h
GELBOORU_DELAY = 3
SEND_DELAY = 60 * 3 # 5m

async def get_posts_from_author(author: str):
    
    print("Getting posts from", author)
    res = []
    gelbooru = Gelbooru(config["gelbooru_api_key"], config["gelbooru_user_id"])
    
    i = 0
    while True:
        temp_results = await gelbooru.search_posts(tags=[author], page=i, limit=LIMIT)
        res += temp_results
        
        if len(temp_results) < LIMIT:
            break
        i += 1
        sleep(GELBOORU_DELAY)
    
    return res
    
async def get_all_posts():
    posts = []
    
    for x in config["authors"]:
        posts += await get_posts_from_author(x)
    
    print("Got", len(posts), "posts") # TODO: use logging library
    
    posts_info = []
    for post in posts:
        posts_info.append({
            "id": int(post),
            "creator": post.creator_id,
            "created": post.created_at.strftime(DATETIME_FORMAT),
            "url": post.file_url,
            "filename": post.filename,
            "rating": post.rating,
            "source": post.source
        })
    
    posts = sorted(posts_info, key=lambda x:x["created"], reverse=False)
    
    with open(ALL_POSTS_PATH, "w", encoding="utf-8") as out_file:
        out_file.write(json.dumps(posts))
        
    return posts

def load_all_posts():
    with open(ALL_POSTS_PATH, "r", encoding="utf-8") as in_file:
        posts = json.loads(in_file.readline())
        
    return posts

def save_sent_ids(input_list):
    with open(SENT_POSTS_PATH, "w", encoding="utf-8") as out_file:
        out_file.write(json.dumps(input_list))
    return len(input_list)

def send_posts(posts, safe_update=False):
    try:
        with open(ALL_POSTS_PATH, "r", encoding="utf-8") as in_file:
            posts = json.loads(in_file.readline())
    except FileNotFoundError:
        return
    
    try:
        with open(SENT_POSTS_PATH, "r", encoding="utf-8") as in_file:
            sent_ids = json.loads(in_file.readline())
    except FileNotFoundError:
        sent_ids = []
    
    i = 0
    for post in posts:
        i += 1
        post_id = post["id"]
        if post_id not in sent_ids:
            print(i, "SENDING POST ID:", post_id, "creator_id:", post["creator"])
            sent_ids.append(post_id)
            
            if safe_update:
                save_sent_ids(sent_ids)
            sleep(SEND_DELAY)
    
    save_sent_ids(sent_ids)
    print("Everything was sent!")
    return sent_ids

## BEGIN COROUTINES FOR ASYNCIO
async def get_posts_coroutine():
    while True:
        posts = await get_all_posts()
        sent = send_posts(posts, safe_update=True)
        
        print(f"get_posts_coroutine(): {len(posts)} post di cui {len(sent)} inviati.")
        sleep(REFRESH_DELAY)

if __name__ == "__main__":
    with open("config.json", "r", encoding="utf-8") as in_file:
        config = json.loads("".join(in_file.readlines()))
        
    
    loop = asyncio.get_event_loop()
    
    loop.run_until_complete(get_posts_coroutine())