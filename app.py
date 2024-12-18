from flask import Flask, render_template, request, jsonify, send_file, session
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from instascrape import Reel
import os
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.urandom(24)
DOWNLOAD_DIR = "downloaded_videos"

class InstagramDownloader:
    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password
        self.session_id = None
        
    def login(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(options=options)
        
        try:
            driver.get('https://www.instagram.com/accounts/login/')
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, 'username'))
            )
            
            driver.find_element(By.NAME, 'username').send_keys(self.username)
            driver.find_element(By.NAME, 'password').send_keys(self.password)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "._aa4b"))
            )
            
            cookies = driver.get_cookies()
            self.session_id = next((cookie['value'] for cookie in cookies if cookie['name'] == 'sessionid'), None)
            return True
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return False
        finally:
            driver.quit()

    def download_video(self, url):
        if not self.session_id:
            raise Exception("Not logged in")
            
        headers = {
            "User-Agent": "Mozilla/5.0",
            "cookie": f'sessionid={self.session_id};'
        }
        
        reel = Reel(url)
        reel.scrape(headers=headers)
        filename = f"video_{int(time.time())}.mp4"
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        reel.download(fp=filepath)
        return filepath

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
        
    downloader = InstagramDownloader(username, password)
    if downloader.login():
        session['session_id'] = downloader.session_id
        return jsonify({"success": True})
    return jsonify({"error": "Login failed"}), 401

@app.route('/download', methods=['POST'])
def download():
    if 'session_id' not in session:
        return jsonify({"error": "Please login first"}), 401
        
    url = request.form.get('url')
    if not url:
        return jsonify({"error": "URL required"}), 400
        
    try:
        downloader = InstagramDownloader()
        downloader.session_id = session['session_id']
        filepath = downloader.download_video(url)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

def cleanup_old_files():
    try:
        current_time = time.time()
        for filename in os.listdir(DOWNLOAD_DIR):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.getctime(filepath) < (current_time - 3600):
                os.remove(filepath)
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")

if __name__ == "__main__":
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    cleanup_old_files()
    app.run(host="0.0.0.0", port=5000)
