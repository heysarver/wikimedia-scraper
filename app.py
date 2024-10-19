import requests
import os
import argparse
from urllib.parse import unquote
import time

USER_AGENT = "WikimediaScraper/1.0 (https://github.com/heysarver/wikimedia-scraper; 22250203+heysarver@users.noreply.github.com)"

def get_files_in_category(category, license_types=["any"], limit=500):
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": min(500, limit)  # API allows max 500 at a time
    }
    headers = {"User-Agent": USER_AGENT}

    files = []
    total_fetched = 0
    api_calls = 0

    while total_fetched < limit:
        api_calls += 1
        start_time = time.time()
        response = requests.get(base_url, params=params, headers=headers)
        end_time = time.time()
        print(f"API call {api_calls} took {end_time - start_time:.2f} seconds")
        
        data = response.json()

        if "query" not in data or "categorymembers" not in data["query"]:
            print(f"Error in API response: {data}")
            break

        for item in data["query"]["categorymembers"]:
            if license_types == ["any"] or check_license(item["title"], license_types):
                files.append(item["title"])
                total_fetched += 1
                if total_fetched >= limit:
                    break

        print(f"Total files found so far: {total_fetched}")

        if "continue" in data and total_fetched < limit:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
        else:
            break

    return files

def check_license(file_title, license_types):
    start_time = time.time()
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "extmetadata",
        "titles": file_title
    }
    headers = {"User-Agent": USER_AGENT}
    
    response = requests.get(base_url, params=params, headers=headers)
    data = response.json()
    
    page = next(iter(data["query"]["pages"].values()))
    if "imageinfo" not in page:
        return False
    
    metadata = page["imageinfo"][0]["extmetadata"]
    if "LicenseShortName" in metadata:
        license_short_name = metadata["LicenseShortName"]["value"]
        for license_type in license_types:
            if normalize_string(license_type) in normalize_string(license_short_name):
                end_time = time.time()
                print(f"License check for {file_title} took {end_time - start_time:.2f} seconds")
                return True

    end_time = time.time()
    print(f"License check for {file_title} took {end_time - start_time:.2f} seconds")
    return False

def normalize_string(s):
    ns = s.lower().replace(" ", "_")
    ns = ''.join(e for e in ns if e.isalnum() or e == "_")
    return ns

def download_file(file_title, output_dir, min_dimension=None):
    start_time = time.time()
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "url|size",
        "titles": file_title
    }
    headers = {"User-Agent": USER_AGENT}
    
    response = requests.get(base_url, params=params, headers=headers)
    data = response.json()
    
    page = next(iter(data["query"]["pages"].values()))
    if "imageinfo" not in page:
        return
    
    file_info = page["imageinfo"][0]
    file_url = file_info["url"]
    file_width = file_info["width"]
    file_height = file_info["height"]
    
    if min_dimension is not None and file_width < min_dimension and file_height < min_dimension:
        print(f"Skipped: {file_title} (Dimensions: {file_width}x{file_height})")
        return
    
    file_name = unquote(file_url.split("/")[-1])
    
    response = requests.get(file_url, headers=headers)
    if response.status_code == 200:
        with open(os.path.join(output_dir, file_name), "wb") as f:
            f.write(response.content)
        end_time = time.time()
        print(f"Downloaded: {file_name} (Dimensions: {file_width}x{file_height}) in {end_time - start_time:.2f} seconds")
    else:
        print(f"Failed to download: {file_name}. Status code: {response.status_code}")

def main():
    parser = argparse.ArgumentParser(description="Download images from Wikimedia Commons categories.")
    parser.add_argument("--category", required=True, help="Category to scrape")
    parser.add_argument("--license", required=False, help="License(s) to filter by, comma separated", default="any")
    parser.add_argument("--output", required=False, help="Output directory", default="output")
    parser.add_argument("--limit", required=False, help="Maximum number of files to scrape", default=500, type=int)
    parser.add_argument("--min-dimension", required=False, help="Minimum width or height of images to download", type=int)
    args = parser.parse_args()

    category = args.category
    license_types = [lt.strip().lower() for lt in args.license.split(",")]
    output_dir = args.output
    file_limit = args.limit
    min_dimension = args.min_dimension

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print(f"Fetching files from category: {category}")
    print(f"License filter: {', '.join(license_types)}")
    print(f"Output directory: {output_dir}")
    print(f"File limit: {file_limit}")
    if min_dimension:
        print(f"Minimum dimension: {min_dimension}")
    else:
        print("No minimum dimension set (downloading all files)")
    
    start_time = time.time()
    files = get_files_in_category(category, license_types, file_limit)
    end_time = time.time()
    print(f"Found {len(files)} files matching criteria in {end_time - start_time:.2f} seconds")

    for index, file in enumerate(files, 1):
        print(f"Processing file {index} of {len(files)}")
        download_file(file, output_dir, min_dimension)
    
    print("Download complete.")

if __name__ == '__main__':
    main()
