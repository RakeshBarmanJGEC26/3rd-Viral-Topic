import streamlit as st
import requests
from datetime import datetime, timedelta
import re

# ==============================
# YouTube API Key
# ==============================
API_KEY = "AIzaSyCC_B5qrb2wibpaNIKtIHqUKv4VXqe0tnw"

YOUTUBE_SEARCH_URL  = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL   = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"

# ==============================
# Streamlit Config
# ==============================
st.set_page_config(page_title="Viral Horror Channel Discovery", layout="wide")
st.title("🎃 Viral Horror Channel Discovery Engine")
st.caption("Manual Keyword Mode · English Only · Adjustable Filters")

# ==============================
# Sidebar — Filters
# ==============================
with st.sidebar:
    st.header("⚙️ Filters")
    days         = st.number_input("Search from last N days:", min_value=1, value=14)
    min_views    = st.number_input("Minimum Views:", min_value=0, value=18000, step=1000)
    max_subs     = st.number_input("Max Subscribers:", min_value=0, value=10000, step=500)
    min_duration = st.number_input("Minimum Duration (minutes):", min_value=1, value=18)

# ==============================
# Keyword Input Area
# ==============================
st.markdown("### 📋 Enter Your Keywords")
st.caption("Paste keywords separated by **commas** or **new lines**. Each keyword = one search pass.")

raw_keywords = st.text_area(
    label="Keywords",
    placeholder="true scary stories\nreal horror narration\nnosleep reddit story, stalker true story\ncreepy encounter at night",
    height=250,
)

# Parse keywords — split by newline or comma, strip whitespace, remove blanks
def parse_keywords(raw):
    lines = raw.replace(",", "\n").splitlines()
    return [k.strip() for k in lines if k.strip()]

keywords = parse_keywords(raw_keywords)

if keywords:
    st.success(f"✅ **{len(keywords)} keyword(s)** loaded and ready.")
    with st.expander("👁 Preview Parsed Keywords"):
        for i, kw in enumerate(keywords, 1):
            st.write(f"{i}. {kw}")
else:
    st.info("⬆️ Paste your keywords above to get started.")

# ==============================
# ISO 8601 Duration Converter
# ==============================
def duration_to_seconds(duration):
    pattern = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')
    match = pattern.match(duration)
    if not match:
        return 0
    hours   = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds

# ==============================
# Hard English-Only Filter
# ==============================
def is_english(text):
    if re.search(r'[\u0900-\u097F]', text): return False  # Devanagari
    if re.search(r'[\u0600-\u06FF]', text): return False  # Arabic/Urdu
    if re.search(r'[\u0980-\u09FF]', text): return False  # Bengali
    if re.search(r'[\u0B80-\u0BFF]', text): return False  # Tamil
    if re.search(r'[\u0C00-\u0C7F]', text): return False  # Telugu
    non_english_markers = [
        'hindi', 'bhoot', 'darr', 'kahani', 'kahaniya',
        'bhutiya', 'darawani', 'bhutni', 'horror hindi',
        'scary hindi', 'hindi horror', 'hindi story',
        'horror urdu', 'urdu horror', 'urdu story',
        'urdu kahani', 'sachi kahani', 'desi horror',
        'pakistani horror', 'indian horror hindi',
        'bhootiya', 'raat ko', 'andheri raat'
    ]
    lower = text.lower()
    for marker in non_english_markers:
        if marker in lower:
            return False
    return True

# ==============================
# Core Fetch & Filter Function
# ==============================
def fetch_and_filter(search_params, seen_ids, min_views, max_subs, min_duration_sec):
    results = []

    try:
        response = requests.get(YOUTUBE_SEARCH_URL, params=search_params, timeout=10)
        data = response.json()
    except Exception:
        return results

    if "items" not in data or not data["items"]:
        return results

    unique_videos = []
    for v in data["items"]:
        vid_id = v["id"].get("videoId")
        title  = v["snippet"].get("title", "")
        if vid_id and vid_id not in seen_ids and is_english(title):
            seen_ids.add(vid_id)
            unique_videos.append(v)

    if not unique_videos:
        return results

    video_ids   = [v["id"]["videoId"] for v in unique_videos]
    channel_ids = list(set([v["snippet"]["channelId"] for v in unique_videos]))

    try:
        video_data = requests.get(YOUTUBE_VIDEO_URL, params={
            "part": "statistics,contentDetails",
            "id"  : ",".join(video_ids),
            "key" : API_KEY
        }, timeout=10).json()

        channel_data = requests.get(YOUTUBE_CHANNEL_URL, params={
            "part": "statistics",
            "id"  : ",".join(channel_ids),
            "key" : API_KEY
        }, timeout=10).json()
    except Exception:
        return results

    if "items" not in video_data or "items" not in channel_data:
        return results

    channel_sub_map = {c["id"]: int(c["statistics"].get("subscriberCount", 0)) for c in channel_data["items"]}
    video_stats_map = {v["id"]: v for v in video_data["items"]}

    for vid in unique_videos:
        vid_id = vid["id"]["videoId"]
        vdata  = video_stats_map.get(vid_id)
        if not vdata:
            continue

        duration_seconds = duration_to_seconds(vdata["contentDetails"]["duration"])
        if duration_seconds < min_duration_sec:
            continue

        views      = int(vdata["statistics"].get("viewCount", 0))
        channel_id = vid["snippet"]["channelId"]
        subs       = channel_sub_map.get(channel_id, 0)

        if views < min_views:
            continue
        if subs >= max_subs:
            continue

        ratio = round(views / subs, 1) if subs > 0 else 0

        results.append({
            "Title"          : vid["snippet"]["title"],
            "Channel"        : vid["snippet"]["channelTitle"],
            "ChannelID"      : channel_id,
            "Published"      : vid["snippet"]["publishedAt"][:10],
            "URL"            : f"https://www.youtube.com/watch?v={vid_id}",
            "Views"          : views,
            "Subscribers"    : subs,
            "Duration (min)" : round(duration_seconds / 60, 2),
            "Views/Sub Ratio": ratio
        })

    return results

# ==============================
# Main Search Button
# ==============================
st.markdown("---")

if not keywords:
    st.button("🚀 Discover Viral Horror Channels", disabled=True)
else:
    if st.button("🚀 Discover Viral Horror Channels"):
        try:
            start_date          = (datetime.utcnow() - timedelta(days=int(days))).isoformat("T") + "Z"
            min_duration_sec    = int(min_duration) * 60
            all_results         = []
            seen_ids            = set()
            discovered_channels = set()

            total_passes = len(keywords)
            progress     = st.progress(0)
            status       = st.empty()

            # ─────────────────────────────────────────
            # PASS 1 — Your Manual Keywords
            # ─────────────────────────────────────────
            st.markdown("### 🔎 Pass 1 — Keyword Search")
            for i, keyword in enumerate(keywords):
                status.write(f"Searching: **{keyword}**")
                progress.progress((i + 1) / total_passes)

                found = fetch_and_filter({
                    "part"             : "snippet",
                    "q"                : keyword,
                    "type"             : "video",
                    "order"            : "viewCount",
                    "publishedAfter"   : start_date,
                    "maxResults"       : 10,
                    "regionCode"       : "US",
                    "relevanceLanguage": "en",
                    "videoDuration"    : "long",
                    "safeSearch"       : "none",
                    "key"              : API_KEY
                }, seen_ids, min_views, max_subs, min_duration_sec)

                all_results.extend(found)
                for r in found:
                    discovered_channels.add(r["ChannelID"])

            # ─────────────────────────────────────────
            # PASS 2 — Channel Deep Dive
            # ─────────────────────────────────────────
            st.markdown("### 🔎 Pass 2 — Channel Deep Dive")
            channel_list = list(discovered_channels)
            for i, channel_id in enumerate(channel_list):
                status.write(f"Deep diving channel {i + 1} of {len(channel_list)}")

                found = fetch_and_filter({
                    "part"          : "snippet",
                    "channelId"     : channel_id,
                    "type"          : "video",
                    "order"         : "viewCount",
                    "publishedAfter": start_date,
                    "maxResults"    : 5,
                    "videoDuration" : "long",
                    "key"           : API_KEY
                }, seen_ids, min_views, max_subs, min_duration_sec)

                all_results.extend(found)

            progress.empty()
            status.empty()

            # Sort by Views/Sub Ratio
            all_results = sorted(all_results, key=lambda x: x["Views/Sub Ratio"], reverse=True)

            # ─────────────────────────────────────────
            # Results Display
            # ─────────────────────────────────────────
            if all_results:
                st.success(f"✅ Found **{len(all_results)}** viral horror videos from small channels")

                for r in all_results:
                    ratio = r["Views/Sub Ratio"]
                    if ratio >= 10:
                        badge = "🔥 MEGA VIRAL"
                    elif ratio >= 5:
                        badge = "⚡ VIRAL"
                    else:
                        badge = "📈 TRENDING"

                    st.markdown(
                        f"### {r['Title']}\n"
                        f"{badge}  \n"
                        f"🕒 **Duration:** {r['Duration (min)']} min  \n"
                        f"👁 **Views:** {r['Views']:,}  \n"
                        f"👥 **Subscribers:** {r['Subscribers']:,}  \n"
                        f"📊 **Views/Sub Ratio:** {ratio}x  \n"
                        f"📅 **Published:** {r['Published']}  \n"
                        f"📺 **Channel:** {r['Channel']}  \n"
                        f"🔗 [Watch Video]({r['URL']})"
                    )
                    st.write("---")
            else:
                st.warning("❌ No matching videos found. Try more keywords or increase the day range.")

        except Exception as e:
            st.error(f"⚠️ Error: {e}")
