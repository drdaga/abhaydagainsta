from flask import Flask, render_template, request, jsonify, send_file
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from instascrape import Reel
import os
import time
import logging

app = Flask(__name__)
session_id = None
DOWNLOAD_DIR = "downloaded_videos"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_instagram_session():
    global session_id
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-notifications')
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries and session_id is None:
        try:
            logger.info(f"Attempting Instagram login (attempt {retry_count + 1}/{max_retries})")
            driver = webdriver.Chrome(options=options)
            driver.get('https://www.instagram.com/accounts/login/')
            
            # Wait for login form
            username_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, 'username'))
            )
            
            # Get credentials from environment
            username = os.getenv('INSTAGRAM_USERNAME')
            password = os.getenv('INSTAGRAM_PASSWORD')
            
            if not username or not password:
                raise ValueError("Instagram credentials not found in environment variables")
            
            # Login process
            username_input.send_keys(username)
            driver.find_element(By.NAME, 'password').send_keys(password)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            
            # Wait for successful login
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "._aa4b"))
            )
            
            # Get session ID
            cookies = driver.get_cookies()
            session_id = next((cookie['value'] for cookie in cookies if cookie['name'] == 'sessionid'), None)
            
            if session_id:
                logger.info("Successfully logged in to Instagram")
                break
                
        except TimeoutException:
            logger.error("Timeout while trying to log in")
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
        finally:
            driver.quit()
            retry_count += 1
            if session_id is None and retry_count < max_retries:
                time.sleep(5)  # Wait before retrying
    
    if session_id is None:
        logger.error("Failed to login after maximum retries")
        raise Exception("Could not establish Instagram session")

@app.route('/')
def home():
    return render_template('index.html', logged_in=(session_id is not None))

@app.route('/status')
def status():
    return jsonify({
        "status": "active" if session_id else "not logged in",
        "logged_in": bool(session_id)
    })

@app.route('/download', methods=['POST'])
def download_video():
    if not session_id:
        return jsonify({"error": "Not logged into Instagram"}), 401
        
    url = request.form.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400
        
    if not url.startswith('https://www.instagram.com/'):
        return jsonify({"error": "Invalid Instagram URL"}), 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "cookie": f'sessionid={session_id};'
        }
        
        reel = Reel(url)
        reel.scrape(headers=headers)
        
        # Create unique filename
        timestamp = int(time.time())
        filename = f"video_{timestamp}.mp4"
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        
        # Ensure download directory exists
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        
        # Download the video
        reel.download(fp=filepath)
        
        if not os.path.exists(filepath):
            raise Exception("Download failed - file not created")
            
        logger.info(f"Successfully downloaded video: {filename}")
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4'
        )
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({"error": f"Failed to download video: {str(e)}"}), 500

@app.route('/refresh-session', methods=['POST'])
def refresh_session():
    try:
        init_instagram_session()
        return jsonify({"message": "Session refreshed successfully"}), 200
    except Exception as e:
        return jsonify({"error": f"Failed to refresh session: {str(e)}"}), 500

def cleanup_old_videos():
    """Clean up videos older than 1 hour"""
    try:
        current_time = time.time()
        for filename in os.listdir(DOWNLOAD_DIR):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.getctime(filepath) < (current_time - 3600):  # 1 hour
                os.remove(filepath)
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")

if __name__ == "__main__":
    # Create downloads directory
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # Initial login
    try:
        init_instagram_session()
    except Exception as e:
        logger.error(f"Initial login failed: {str(e)}")
    
    # Start the Flask app
    app.run(host="0.0.0.0", port=5000)
