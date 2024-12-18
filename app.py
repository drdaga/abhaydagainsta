from flask import Flask, render_template, request, jsonify, send_file
import os
import time
from instascrape import Reel
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
DOWNLOAD_DIR = "downloaded_videos"

class InstagramDownloader:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "cookie": f'sessionid={os.getenv("INSTAGRAM_SESSION_ID")};'
        }

    def download_video(self, url):
        try:
            reel = Reel(url)
            reel.scrape(headers=self.headers)
            timestamp = int(time.time())
            filename = f"video_{timestamp}.mp4"
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            reel.download(fp=filepath)
            return filepath
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            raise

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download_video():
    try:
        url = request.form.get('url')
        if not url:
            return jsonify({"error": "No URL provided"}), 400

        if not url.startswith('https://www.instagram.com/'):
            return jsonify({"error": "Invalid Instagram URL"}), 400

        downloader = InstagramDownloader()
        filepath = downloader.download_video(url)
        
        if not os.path.exists(filepath):
            return jsonify({"error": "Download failed"}), 500

        return send_file(
            filepath,
            as_attachment=True,
            download_name=os.path.basename(filepath),
            mimetype='video/mp4'
        )

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/status')
def status():
    session_id = os.getenv("INSTAGRAM_SESSION_ID")
    return jsonify({
        "status": "active" if session_id else "not configured",
        "download_dir": os.path.exists(DOWNLOAD_DIR)
    })

def cleanup_old_files():
    """Clean up files older than 1 hour"""
    try:
        current_time = time.time()
        for filename in os.listdir(DOWNLOAD_DIR):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.getctime(filepath) < (current_time - 3600):
                os.remove(filepath)
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")

def init_app():
    """Initialize application settings"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if not os.getenv("INSTAGRAM_SESSION_ID"):
        logger.warning("INSTAGRAM_SESSION_ID environment variable not set")

if __name__ == "__main__":
    init_app()
    app.run(host="0.0.0.0", port=5000)
