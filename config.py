# devgagan
# Note if you are trying to deploy on vps then directly fill values in ("")

from os import getenv

# VPS --- FILL COOKIES 🍪 in """ ... """ 

INST_COOKIES = """
# wtite up here insta cookies
"""

YTUB_COOKIES = """
# write here yt cookies
"""

API_ID = int(getenv("API_ID", "20348897"))
API_HASH = getenv("API_HASH", "ecfb9a700b8398caf58c53f36ccf5b06")
BOT_TOKEN = getenv("BOT_TOKEN","8037339627:AAG92sWh1gQwDGtdaJJ_X916otdY5eCd9n4")
OWNER_ID = list(map(int, getenv("OWNER_ID", "5464921200").split()))
MONGO_DB = getenv("MONGO_DB", "mongodb+srv://PihuMusic:PihuMusic@cluster0.w3eiu.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
LOG_GROUP = getenv("LOG_GROUP", "-1002283846449")
CHANNEL_ID = int(getenv("CHANNEL_ID", "-1001573605549"))
FREEMIUM_LIMIT = int(getenv("FREEMIUM_LIMIT", "500"))
PREMIUM_LIMIT = int(getenv("PREMIUM_LIMIT", "500"))
WEBSITE_URL = getenv("WEBSITE_URL", "upshrink.com")
AD_API = getenv("AD_API", "52b4a2cf4687d81e7d3f8f2b7bc2943f618e78cb")
STRING = getenv("STRING", None)

# YouTube Cookies Configuration (ensure to replace this with valid cookies)
#YT_COOKIES = getenv("YT_COOKIES", "GPS=1; YSC=VW83QNuF-rE; __Secure-ROLLOUT_TOKEN=CPfXrsuG1-m97gEQ-L_JhfWBiwMY-L_JhfWBiwM%3D; VISITOR_INFO1_LIVE=myhtpsWPqDg; VISITOR_PRIVACY_METADATA=CgJJThIEGgAgUg%3D%3D; PREF>

# Instagram Cookies (if required)
#INSTA_COOKIES = getenv("INSTA_COOKIES", None)
