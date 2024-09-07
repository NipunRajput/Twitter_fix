from flask import Flask, render_template, request, send_file, redirect, url_for, flash
import os
import secrets  # For generating a secure random key
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Define the directories for screenshots and text files
screenshot_dir = os.path.join("static", "tweet_screenshots")
text_dir = os.path.join("static", "tweet_texts")

# Make sure both directories exist
os.makedirs(screenshot_dir, exist_ok=True)
os.makedirs(text_dir, exist_ok=True)

# Set the secret key for session management
app.secret_key = secrets.token_hex(16)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_url():
    profile_url = request.form.get('profile_url')

    if not profile_url:
        flash("Please provide an X.com profile URL.")
        return redirect(url_for('index'))

    # Call the function to process the profile
    try:
        profile_data = scrape_profile(profile_url)
        tweet_id = profile_data.get("id", "unknown")
        return render_template('result.html', 
                               image_path=profile_data['screenshot'],
                               text_path=profile_data['text_file'],
                               text=profile_data['text'])
    except Exception as e:
        flash(f"Error processing the X.com profile: {e}")
        return redirect(url_for('index'))

def scrape_profile(url: str) -> dict:
    """
    Scrape an X.com profile details, fetch the post (tweet), and capture a screenshot.
    Save the tweet text into a .txt file.
    If no tweets are found, take a screenshot and save all visible text from the page.
    """
    _xhr_calls = []

    def intercept_response(response):
        """Capture all background requests (XHR) and save them"""
        if response.request.resource_type == "xhr":
            _xhr_calls.append(response)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)  # Launch browser in headless mode
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # Enable background request intercepting
        page.on("response", intercept_response)
        
        # Go to the profile URL
        page.goto(url)
        page.wait_for_selector("[data-testid='primaryColumn']")  # Wait for profile to load

        # Wait for the profile to appear on the page
        page.wait_for_timeout(3000)

        # Try to extract the first tweet and capture a screenshot
        tweet_element = page.query_selector(f'[data-testid="tweet"]')
        tweet_id = url.split('/')[-1]  # Get tweet ID from URL

        if tweet_element:
            # Extract tweet text
            tweet_text = tweet_element.text_content()

            # Take screenshot of the tweet
            screenshot_path = os.path.join(screenshot_dir, f"tweet_{tweet_id}.png")
            tweet_element.screenshot(path=screenshot_path)

            # Save tweet text into a .txt file
            text_file_path = os.path.join(text_dir, f"tweet_{tweet_id}.txt")
            with open(text_file_path, "w", encoding="utf-8") as text_file:
                text_file.write(tweet_text.strip())

            return {
                "id": tweet_id,
                "text": tweet_text.strip(),
                "screenshot": screenshot_path,
                "text_file": text_file_path
            }
        else:
            # If no tweets are found, capture a screenshot of the page and save the visible text
            screenshot_path = os.path.join(screenshot_dir, f"page_{tweet_id}.png")
            page.screenshot(path=screenshot_path)

            # Extract all visible text from the page
            page_text = page.text_content().strip()

            # Save the extracted page text into a .txt file
            text_file_path = os.path.join(text_dir, f"page_{tweet_id}.txt")
            with open(text_file_path, "w", encoding="utf-8") as text_file:
                text_file.write(page_text)

            return {
                "id": tweet_id,
                "text": page_text,
                "screenshot": screenshot_path,
                "text_file": text_file_path
            }

@app.route('/download_image/<filename>')
def download_image(filename):
    file_path = os.path.join(screenshot_dir, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        # If the file does not exist, show a flash message
        flash(f"File {filename} not found. Please make sure the file exists.")
        return redirect(url_for('index'))

@app.route('/download_text/<filename>')
def download_text(filename):
    file_path = os.path.join(text_dir, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        # If the file does not exist, show a flash message
        flash(f"File {filename} not found. Please make sure the file exists.")
        return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)
