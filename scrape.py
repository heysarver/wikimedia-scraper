import os
import requests
import time

# Wikimedia Commons API URL
WIKI_API_URL = "https://commons.wikimedia.org/w/api.php"
CATEGORY_NAME = "Category:Logos_of_companies"
IMAGE_DIR = "./images"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
MAX_IMAGES = 10000  # Number of images to download
CMLIMIT = 500  # API limit per request (500 for non-logged-in users)

# Create the directory to store images if it doesn't exist
if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

def get_images_from_category(category):
    """Fetch images from the specified category using pagination."""
    images = []
    continue_token = None
    
    while len(images) < MAX_IMAGES:
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": "file",
            "cmlimit": CMLIMIT  # Max 500 per query
        }

        # Add continue token to the request if available
        if continue_token:
            params["cmcontinue"] = continue_token

        response = requests.get(WIKI_API_URL, params=params, headers={"User-Agent": USER_AGENT})
        data = response.json()
        
        if 'query' in data:
            images.extend(data['query']['categorymembers'])
        else:
            break  # Stop if no more results
        
        # Check for pagination (continue) token
        if 'continue' in data:
            continue_token = data['continue']['cmcontinue']
        else:
            break  # No more pages

        print(f"Retrieved {len(images)} images so far...")

    return images[:MAX_IMAGES]  # Return only up to MAX_IMAGES

def get_image_info(image_title):
    """Get detailed information about the image such as resolution and license."""
    params = {
        "action": "query",
        "format": "json",
        "titles": image_title,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata|user|canonicaltitle|mediatype|mime"
    }
    
    response = requests.get(WIKI_API_URL, params=params, headers={"User-Agent": USER_AGENT})
    data = response.json()
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        if "imageinfo" in page:
            return page["imageinfo"][0]
    return None

def download_image(image_url, image_title):
    """Download the image and save it locally."""
    try:
        image_data = requests.get(image_url, headers={"User-Agent": USER_AGENT}, allow_redirects=True)
        image_data.raise_for_status()  # Check for HTTP errors
        file_name = os.path.join(IMAGE_DIR, image_title.split(':')[-1])
        
        with open(file_name, 'wb') as image_file:
            image_file.write(image_data.content)
            print(f"Downloaded {file_name}")
    except requests.exceptions.RequestException as e:
        print(f"Failed to download {image_title} from {image_url}: {e}")

def filter_images(images):
    """Filter images based on resolution and public domain license."""
    for image in images:
        image_info = get_image_info(image["title"])
        if image_info:
            width = image_info.get("width", 0)
            height = image_info.get("height", 0)
            extmetadata = image_info.get("extmetadata", {})
            license_info = extmetadata.get("License", {}).get("value", "Unknown License")
            image_url = image_info["url"]

            # Check if either width or height is at least 1024, and check for public domain license
            if (width >= 1024 or height >= 1024) and ("pd" in license_info.lower() or "cc0" in license_info.lower()):
                # Debug output for license, resolution, and URL
                print(f"Image: {image['title']}")
                print(f"  License: {license_info}")
                print(f"  Resolution: {width}x{height}")
                print(f"  URL: {image_url}")
                download_image(image_url, image["title"])
                time.sleep(1)  # Add delay to prevent rate limiting

def main():
    # Fetch images from the specified category with pagination
    images = get_images_from_category(CATEGORY_NAME)
    
    if images:
        print(f"Found {len(images)} images. Filtering by resolution and license...")
        filter_images(images)
    else:
        print("No images found in the specified category.")

if __name__ == "__main__":
    main()
