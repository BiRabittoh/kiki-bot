import requests, logging, json
from time import sleep
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 3
MAX_RETRIES = 3
BASE_POST_URL = "https://gelbooru.com/index.php?page=post&s=view&id="

def telegram_request(payload, post, token, method="sendMessage"):
    
    i = 0
    while i < MAX_RETRIES:
        request_url = 'https://api.telegram.org/bot{0}/{1}'.format(token, method)
        r = requests.post(url=request_url, data=payload).json()
        
        if r['ok']:
            return r
        i += 1
        logger.warn(f"{i}: {r}")
        logger.debug(f"{i}: {payload}")
        sleep(REQUEST_TIMEOUT)
    
    return telegram_request({
                            'chat_id': payload['chat_id'],
                            'text': f"[{post['creator']}]({BASE_POST_URL}{post['id']})",
                            'parse_mode': 'markdown'
                            }, post=post, token=token) 

def send_post_telegram(post, bot_token, chat_id):
    
    extension = post["filename"].split(".")[-1]
    link = post["url"]
    reply_markup = json.dumps({ "inline_keyboard": [[{ "text": f"🍝 {post['creator']}", "url": BASE_POST_URL + str(post['id']) }]]})
    
    r = None
    match extension:
        case "jpeg" | "jpg" | "png":
            r = telegram_request({ 'chat_id': chat_id, 'photo': link, 'reply_markup': reply_markup },
                                 post=post, token=bot_token, method="sendPhoto")
        case "gif" | "mp4":
            r = telegram_request({ 'chat_id': chat_id, 'video': link, 'reply_markup': reply_markup },
                                 post=post, token=bot_token, method="sendVideo")
        case _:
            logger.debug(f"Unhandled extension {extension} for link: {link}.")
            r = telegram_request({ 'chat_id': chat_id, 'text': f"[Unknown extension]({link}).", 'parse_mode': 'markdown' },
                                 post=post, token=bot_token)
    return r
