from pygelbooru import Gelbooru, GelbooruException
from time import sleep
from datetime import datetime
from Bot import send_post_telegram
from json import loads, dumps, JSONDecodeError
from iteration_utilities import unique_everseen

import asyncio, logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_PATH = "config.json"
SENT_POSTS_PATH = "sent_posts.json"
POSTS_PATH = "posts.json"
GELBOORU_LIMIT = 100 # must be 100 or under
GELBOORU_MAX_RETRIES = 3
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ%z"

def load_json_else_empty(path, failed_callback=lambda:None):
    try:
        with open(path, "r", encoding="utf-8") as in_file:
            return loads("".join(in_file.readlines()))
    except FileNotFoundError:
        logging.warning(f"The following file was not found: {path}.")
        failed_callback()
        return []
    except JSONDecodeError:
        logging.warning(f"JSON decode failed for the following file: {path}.")
        failed_callback()
        return []

def load_posts_if_present():
    
    posts = load_json_else_empty(POSTS_PATH)
    for post in posts:
        post["created"] = datetime.strptime(post["created"], DATETIME_FORMAT)
    return posts
    
def update_posts(posts):
    
    for post in posts:
        post["created"] = post["created"].strftime(DATETIME_FORMAT) # convert time to string
    
    save_json_to_file(posts, POSTS_PATH)
    return len(posts)

async def get_posts_from_authors(gelbooru, authors, tags, exclude_tags):
    
    if len(authors) == 1:
        query_tags = list(authors)
    else:
        tagstring = "{" + ' ~ '.join(authors) + "}"
        query_tags = tagstring.split() + tags
        
    logger.debug(f"tags: {query_tags}; exclude_tags: {exclude_tags}")
    
    new_posts = []
    page = 0
    try_count = 0
    
    while True:
        logger.debug(f"Asking for page {page}.")
        try:
            temp_results = await gelbooru.search_posts(tags=query_tags, exclude_tags=exclude_tags, page=page, limit=GELBOORU_LIMIT)
            logger.info(f"Got {len(temp_results)} posts from page {page}.")
            new_posts += temp_results
            try_count = 0
        
            if len(temp_results) < GELBOORU_LIMIT:
                break
            page += 1
            sleep(GELBOORU_DELAY)
        except GelbooruException:
            try_count += 1
            if try_count > GELBOORU_MAX_RETRIES:
                break
            logger.warning(f"Got an error on try {try_count} for page {page}. Retrying soon...")
            sleep(GELBOORU_DELAY * 10)
    
    logger.info(f"Got {len(new_posts)} new posts.")
    
    new_posts_info = []
    for post in new_posts:
        post_authors = [x for x in post.tags if x in authors]
        new_posts_info.append({
            "id": int(post),
            "creator": ", ".join(post_authors),
            "created": post.created_at,
            "url": post.file_url,
            "filename": post.filename,
            "rating": post.rating,
            "source": post.source
        })
    return new_posts_info

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    return [lst[i:i + n] for i in range(0, len(lst), n)]

async def get_all_posts():

    logger.debug("Config:" + str(config))
    gelbooru = Gelbooru(config["gelbooru_api_key"], config["gelbooru_user_id"])
    
    authors = sorted(set(config["authors"]))
    logger.info(f"Authors: {authors}")
    authors = chunks(authors, GELBOORU_MAX_AUTHORS)
    
    new_posts_info = []
    for split in authors:
        new_posts_info += await get_posts_from_authors(gelbooru, split, config["tags"], config["exclude_tags"])
        
    posts = list(unique_everseen(posts + new_posts_info)) # remove duplicates
    posts.sort(key=lambda x:x["created"], reverse=False) # sort posts
    
    n = update_posts(posts)
    logging.debug(f"Finished saving {n} posts to {POSTS_PATH}.")
    return posts

def save_json_to_file(obj, path):
    
    with open(path, "w", encoding="utf-8") as out_file:
        out_file.write(dumps(obj))

def send_post(post):
    sent_ids = load_json_else_empty(SENT_POSTS_PATH)
    post_id = post["id"]
    
    if post_id not in sent_ids:
        logger.info(f'Sending post id {post_id}, by creator {post["creator"]}.')
        r = send_post_telegram(post, bot_token, chat_id)
        logger.debug(f'Request output -> {r}')
        
        sent_ids.append(post_id)
        save_json_to_file(sent_ids, SENT_POSTS_PATH)
        sleep(SEND_DELAY)

    return True

## BEGIN COROUTINES FOR ASYNCIO
async def get_posts_coroutine():

    errors = []
    i = 1
    while True:
        posts = await get_all_posts()
        
        sent = 0
        for post in posts:
            if send_post(post):
                sent += 1
            else:
                errors.append(post)
                logging.error(f"Couldn't send post {post['id']}.")
    
        logger.info(f"Sent {sent}/{len(posts)} posts.")
        logger.info(f"Errors: {errors}")
        sleep(REFRESH_DELAY)

if __name__ == "__main__":
    
    config = load_json_else_empty(CONFIG_PATH, lambda:exit(1))
        
    chat_id = config["chat_id"]
    bot_token = config["bot_token"]
    if chat_id == "" or bot_token == "":
        logger.error(f"Please check your {CONFIG_PATH}.")
        exit(1)
        
    REFRESH_DELAY = config["refresh_delay"] #60 * 60 # 1h
    GELBOORU_DELAY = config["gelbooru_delay"] #3
    GELBOORU_MAX_AUTHORS = config["gelbooru_max_authors"] # 10
    SEND_DELAY = config["send_delay"]# 60 * 3 # 3m
        
    loop = asyncio.get_event_loop()
    loop.run_until_complete(get_posts_coroutine())
