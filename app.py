import os
import requests
from urllib.parse import urlparse
import argparse
from PIL import Image, UnidentifiedImageError, ImageEnhance
from io import BytesIO

# Wikimedia API URL to get images from a specific category
WIKIMEDIA_API_URL = "https://commons.wikimedia.org/w/api.php"

# Function to fetch images from a category with pagination support
def fetch_images_from_category(category, limit=50, min_resolution=0):
    images = []
    continue_param = None
    total_fetched = 0

    while total_fetched < limit:
        params = {
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": f"Category:{category}",
            "gcmtype": "file",
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|size",
            "format": "json",
            "gcmlimit": min(50, limit - total_fetched)  # Limit each batch, respecting total limit
        }

        if continue_param:
            params["gcmcontinue"] = continue_param

        response = requests.get(WIKIMEDIA_API_URL, params=params)
        data = response.json()

        if "query" in data:
            pages = data["query"]["pages"]
            for page_id, page in pages.items():
                image_info = page.get("imageinfo", [])
                if image_info:
                    metadata = image_info[0]["extmetadata"]
                    license_short_name = metadata.get("LicenseShortName", {}).get("value", "")
                    width = image_info[0].get("width", 0)
                    height = image_info[0].get("height", 0)

                    # Filter for public domain images (Public domain or CC0 licenses)
                    # and check if at least one dimension meets the minimum resolution
                    if ("public domain" in license_short_name.lower() or "cc0" in license_short_name.lower()) and \
                       (width >= min_resolution or height >= min_resolution):
                        images.append({
                            "title": page["title"],
                            "url": image_info[0]["url"],
                            "license": license_short_name,
                            "description": metadata.get("ImageDescription", {}).get("value", "No description available.")
                        })
                        total_fetched += 1

                        # If we've hit the limit, stop
                        if total_fetched >= limit:
                            break

        # Handle pagination
        if "continue" in data:
            continue_param = data["continue"]["gcmcontinue"]
        else:
            break

    return images

# Function to get the file extension from the image URL
def get_file_extension(url):
    path = urlparse(url).path
    return os.path.splitext(path)[1]

# Function to determine the background color based on the argument
def get_background_color(bg_color):
    if bg_color == 'white':
        return (255, 255, 255), 'RGB'
    elif bg_color == 'black':
        return (0, 0, 0), 'RGB'
    elif bg_color == 'transparent':
        return (0, 0, 0, 0), 'RGBA'
    else:
        raise ValueError(f"Unsupported background color: {bg_color}")

# Function to resize proportionally and pad the image to 1024x1024 with specified background
def resize_and_pad_image(img, target_size=(1024, 1024), bg_color='white'):
    background_color, mode = get_background_color(bg_color)

    # Resize image proportionally
    img.thumbnail(target_size, Image.Resampling.LANCZOS)  # Proportional resize using high-quality resampling

    # Create a new background image with the specified color
    new_img = Image.new(mode, target_size, background_color)

    # Get position to paste the resized image onto the background (center it)
    paste_position = (
        (target_size[0] - img.width) // 2,
        (target_size[1] - img.height) // 2
    )

    # Paste the resized image onto the background
    new_img.paste(img, paste_position, img if img.mode == 'RGBA' and bg_color == 'transparent' else None)

    return new_img

def resize_image_conditionally(img):
    """Resizes the image if it's below 500px or 200px in any dimension."""
    width, height = img.size

    if width < 200 or height < 200:
        # Quadruple the size
        print(f"Image is smaller than 200px in one or both dimensions, quadrupling size.")
        img = img.resize((width * 4, height * 4), Image.Resampling.NEAREST)
    elif width < 500 or height < 500:
        # Double the size
        print(f"Image is smaller than 500px in one or both dimensions, doubling size.")
        img = img.resize((width * 2, height * 2), Image.Resampling.NEAREST)
    
    return img

def save_standardized_image(image, output_folder, target_size=(1024, 1024), bg_color='white'):
    # Ensure the output folder exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Create a valid filename from the image title, removing the original file extension
    filename = image["title"].replace("File:", "").replace(" ", "_").rsplit(".", 1)[0]
    image_path = os.path.join(output_folder, f"{filename}.png")  # Save all as .png
    description_path = os.path.join(output_folder, f"{filename}.txt")
    
    try:
        # Download the image data
        response = requests.get(image["url"])
        
        img = Image.open(BytesIO(response.content))

        # Conditionally resize based on the dimensions of the image
        img = resize_image_conditionally(img)

        # Convert the image to RGB or RGBA and resize proportionally with specified background padding
        img = img.convert("RGBA") if bg_color == 'transparent' else img.convert("RGB")
        img = resize_and_pad_image(img, target_size, bg_color)

        # Save the standardized image as PNG
        img.save(image_path, format="PNG")

        # Save only the description in the text file
        with open(description_path, 'w') as handler:
            handler.write(image['description'])

        print(f"Saved and standardized image: {filename}.png")

    except UnidentifiedImageError:
        print(f"Failed to process image: {image['title']} from URL: {image['url']} (Unidentified Image)")
    except Exception as e:
        print(f"Error downloading or processing {image['title']}: {str(e)}")

# Main function to start the scraping and processing
def main(category, limit, save, bg_color, min_resolution):
    images = fetch_images_from_category(category, limit, min_resolution)
    
    if images:
        print(f"Found {len(images)} public domain images in the category '{category}':\n")
        for image in images:
            print(f"Title: {image['title']}")
            print(f"URL: {image['url']}")
            print(f"License: {image['license']}")
            print("-" * 60)
            # If save argument is True, save the standardized images and their descriptions
            if save:
                save_standardized_image(image, "output", target_size=(1024, 1024), bg_color=bg_color)
    else:
        print(f"No public domain images found in the category '{category}'.")

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Scrape public domain images from Wikimedia Commons.')
    parser.add_argument('--min-resolution', type=int, help='Minimum width or height resolution for images', default=0)
    parser.add_argument('--limit', type=int, default=50, help='Limit the number of images to scrape (default: 50)')
    parser.add_argument('--save', action='store_true', help='Save and standardize the images to the "output" folder')
    parser.add_argument('--bg-color', choices=['white', 'black', 'transparent'], default='white', 
                        help='Background color to use for padding (white, black, or transparent)')
    args = parser.parse_args()

    # Category to scrape (fixed for this use case)
    category = "Logos_of_companies"

    # Call the main function with arguments
    main(category, args.limit, args.save, args.bg_color, args.min_resolution)
