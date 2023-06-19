from pygelbooru import Gelbooru
from time import sleep
from datetime import datetime
from Bot import send_post_telegram
import requests, json, asyncio, logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S%z"
ALL_POSTS_PATH = "all_posts.json"
SENT_POSTS_PATH = "sent_posts.json"
LIMIT = 100
REFRESH_DELAY = 60 * 60 # 1h
GELBOORU_DELAY = 3
SEND_DELAY = 60 * 3 # 3m
    
async def get_all_posts():

    logging.debug("Config:" + str(config))
    gelbooru = Gelbooru(config["gelbooru_api_key"], config["gelbooru_user_id"])
    
    posts = []
    i = 0
    while True:
        logging.debug(f"Asking for page {i}.")
        temp_results = await gelbooru.search_posts(tags=config["tags"], page=i, limit=LIMIT)
        posts += temp_results
        
        if len(temp_results) < LIMIT:
            break
        i += 1
        sleep(GELBOORU_DELAY)
    
    logging.info(f"Got {len(posts)} posts.")
    
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
        
    return sorted(posts_info, key=lambda x:x["created"], reverse=False)

def save_sent_ids(input_list):
    
    with open(SENT_POSTS_PATH, "w", encoding="utf-8") as out_file:
        out_file.write(json.dumps(input_list))
    return len(input_list)

def send_posts(posts, safe_update=False):
    
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
            logging.debug(f'{i}: SENDING POST ID {post_id}, CREATOR: {post["creator"]}')
            send_post_telegram(post, bot_token, chat_id)
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
        
        logging.debug(f"get_posts_coroutine(): {len(posts)} post di cui {len(sent)} inviati.")
        sleep(REFRESH_DELAY)

if __name__ == "__main__":
    
    try:
        with open("config.json", "r", encoding="utf-8") as in_file:
            config = json.loads("".join(in_file.readlines()))
    except FileNotFoundError:
        logging.error("Please create a file named config.json in this folder.")
        exit(1)
        
    chat_id = config["chat_id"]
    bot_token = config["bot_token"]
    if chat_id == "" or bot_token == "":
        logging.error("Please check your config.json.")
        exit(1)
        
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_posts_coroutine())
