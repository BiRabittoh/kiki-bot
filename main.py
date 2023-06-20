from pygelbooru import Gelbooru, GelbooruException
from time import sleep
from Bot import send_post_telegram
import requests, json, asyncio, logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

SENT_POSTS_PATH = "sent_posts.json"
POSTS_PATH = "posts.json"
GELBOORU_LIMIT = 100 # must be 100 or under
GELBOORU_MAX_RETRIES = 3

first_load = True
async def get_all_posts():
    global first_load
    
    if first_load:
        try:
            with open(POSTS_PATH, "r", encoding="utf-8") as in_file:
                posts = json.loads(in_file.readline())
                first_load = False
                return posts
        except FileNotFoundError:
            logger.info(f"{POSTS_PATH} file not found. Let's create it.")

    logger.debug("Config:" + str(config))
    gelbooru = Gelbooru(config["gelbooru_api_key"], config["gelbooru_user_id"])
    
    authors = sorted(set(config["authors"]))
    logger.info(f"Authors: {authors}")
    if len(authors) == 1:
        tags = list(authors)
    else:
        tagstring = "{" + ' ~ '.join(authors) + "}"
        tags = tagstring.split() + config["tags"]
    exclude_tags = config["exclude_tags"]
    logger.info(f"tags: {tags}; exclude_tags: {exclude_tags}")
    
    posts = []
    page = 0
    while True:
        
        try_count = 0
        logger.debug(f"Asking for page {page}.")
        try:
            temp_results = await gelbooru.search_posts(tags=tags, exclude_tags=exclude_tags, page=page, limit=GELBOORU_LIMIT)
            logger.info(f"Got {len(temp_results)} posts from page {page}.")
            posts += temp_results
        
            if len(temp_results) < GELBOORU_LIMIT or try_count > GELBOORU_MAX_RETRIES:
                break
            page += 1
            sleep(GELBOORU_DELAY)
        except GelbooruException:
            try_count += 1
            logger.warning(f"Got an error on try {try_count} for page {page}. Retrying soon...")
            sleep(GELBOORU_DELAY * 10)
    
    logger.info(f"Got {len(posts)} posts.")
    
    posts_info = []
    for post in posts:
        posts_info.append({
            "id": int(post),
            "creator": post.tags[0],
            "created": post.created_at,
            "url": post.file_url,
            "filename": post.filename,
            "rating": post.rating,
            "source": post.source
        })
        
    posts = sorted(posts_info, key=lambda x:x["created"], reverse=False)
    
    with open(POSTS_PATH, "w", encoding="utf-8") as out_file:
        text_content = json.dumps([{key : val for key, val in sub.items() if key != "created"} for sub in posts])
        out_file.write(text_content)
    first_load = False
    return posts

def save_sent_ids(input_list):
    
    with open(SENT_POSTS_PATH, "w", encoding="utf-8") as out_file:
        out_file.write(json.dumps(input_list))
    return len(input_list)

def send_posts(posts, safe_update=False):

    i = 0
    for post in posts:
        
        try:
            with open(SENT_POSTS_PATH, "r", encoding="utf-8") as in_file:
                sent_ids = json.loads(in_file.readline())
        except FileNotFoundError:
            sent_ids = []
        
        i += 1
        post_id = post["id"]
        if post_id not in sent_ids:
            logger.info(f'{i}: Sending post id {post_id}, by creator {post["creator"]}.')
            r = send_post_telegram(post, bot_token, chat_id)
            logger.debug(f'{i}: Request output -> {r}')
            sent_ids.append(post_id)
            
            if safe_update:
                save_sent_ids(sent_ids)
            sleep(SEND_DELAY)
    
    save_sent_ids(sent_ids)
    logger.info("Everything was sent!")
    return sent_ids

## BEGIN COROUTINES FOR ASYNCIO
async def get_posts_coroutine():

    i = 1
    while True:
        posts = await get_all_posts()
        sent = send_posts(posts, safe_update=True)
        
        logger.debug(f"{i}: {len(posts)} post di cui {len(sent)} inviati.")
        sleep(REFRESH_DELAY)

if __name__ == "__main__":
    
    try:
        with open("config.json", "r", encoding="utf-8") as in_file:
            config = json.loads("".join(in_file.readlines()))
    except FileNotFoundError:
        logger.error("Please create a file named config.json in this folder.")
        exit(1)
        
    chat_id = config["chat_id"]
    bot_token = config["bot_token"]
    if chat_id == "" or bot_token == "":
        logger.error("Please check your config.json.")
        exit(1)
        
    REFRESH_DELAY = config["refresh_delay"] #60 * 60 # 1h
    GELBOORU_DELAY = config["gelbooru_delay"] #3
    SEND_DELAY = config["send_delay"]# 60 * 3 # 3m
        
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_posts_coroutine())
