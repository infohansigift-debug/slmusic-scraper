import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, unquote
import json
import re
import os
from datetime import datetime

# Config
BASE_URL = "https://www.livehitzmp3.com"
SEARCH_URL = "https://www.livehitzmp3.com/search"  # හෝ homepage
OUTPUT_FILE = "songs.json"
MAX_POSTS = 50  # හැම run එකකදී check කරන posts ගාන

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36"
}

def get_post_links():
    """Homepage එකෙන් latest post links ගන්න"""
    try:
        res = requests.get(BASE_URL, headers=headers, timeout=30)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # මේක later confirm කරන්න ඕන — LiveHitzMP3 එකේ structure එක අනුව
        # සාමාන්‍යයෙන් Blogger template එකක නම්: h2.post-title a, h3.post-title a
        links = []
        for a in soup.select("h2 a, h3 a, .post-title a, .entry-title a"):
            href = a.get("href", "")
            if href and "/20" in href and href.endswith(".html"):
                full_url = urljoin(BASE_URL, href)
                if full_url not in links:
                    links.append(full_url)
        return links[:MAX_POSTS]
    except Exception as e:
        print(f"Error getting post links: {e}")
        return []

def scrape_post(post_url):
    """එක post එකකින් MP3 links ගන්න"""
    try:
        res = requests.get(post_url, headers=headers, timeout=30)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # Post title
        title_tag = soup.select_one("h1, .post-title, .entry-title")
        post_title = title_tag.get_text(strip=True) if title_tag else "Unknown"

        # Post date
        date_tag = soup.select_one("time, .post-date, .published")
        post_date = date_tag.get_text(strip=True) if date_tag else ""

        # Post image (thumbnail)
        img_tag = soup.select_one("img")
        post_image = ""
        if img_tag:
            post_image = img_tag.get("src", "")
            if post_image and not post_image.startswith("http"):
                post_image = urljoin(post_url, post_image)

        # MP3 links — <a href="...mp3">
        mp3_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".mp3") or "livehitz.com" in href and ".mp3" in href:
                # URL decode කරන්න (spaces, special chars)
                clean_url = href.replace(" ", "%20")
                song_name = a.get_text(strip=True) or unquote(href.split("/")[-1])
                mp3_links.append({
                    "title": song_name,
                    "url": clean_url
                })

        if not mp3_links:
            return None

        return {
            "post_title": post_title,
            "post_url": post_url,
            "post_date": post_date,
            "post_image": post_image,
            "songs": mp3_links,
            "scraped_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"Error scraping {post_url}: {e}")
        return None

def load_existing():
    """දැනට තියෙන songs.json එක load කරන්න"""
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"albums": [], "last_updated": None}

def save_data(data):
    """songs.json එකට save කරන්න"""
    data["last_updated"] = datetime.utcnow().isoformat()
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("🚀 LiveHitzMP3 scraper starting...")

    existing = load_existing()
    existing_urls = {album["post_url"] for album in existing.get("albums", [])}

    post_links = get_post_links()
    print(f"📄 Found {len(post_links)} post links")

    new_albums = []
    for i, link in enumerate(post_links, 1):
        if link in existing_urls:
            print(f"[{i}] ⏭️  Skipping (already have): {link}")
            continue

        print(f"[{i}] 🔍 Scraping: {link}")
        album = scrape_post(link)
        if album:
            new_albums.append(album)
            print(f"    ✅ Found {len(album['songs'])} songs")

    # අලුත් ඒවා ඉස්සරහට දාන්න
    all_albums = new_albums + existing.get("albums", [])

    # Duplicate remove (post_url අනුව)
    seen = set()
    unique_albums = []
    for album in all_albums:
        if album["post_url"] not in seen:
            seen.add(album["post_url"])
            unique_albums.append(album)

    data = {"albums": unique_albums}
    save_data(data)

    total_songs = sum(len(a["songs"]) for a in unique_albums)
    print(f"\n✅ Done! {len(new_albums)} new albums, {total_songs} total songs")
    print(f"📁 Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()