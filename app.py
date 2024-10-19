import requests
import os
import argparse
from urllib.parse import unquote
import time
import json

USER_AGENT = "WikimediaScraper/1.0 (https://github.com/heysarver/wikimedia-scraper; 22250203+heysarver@users.noreply.github.com)"

def get_files_in_category(category, license_types=["any"], limit=500):
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmtype": "file",
        "cmlimit": min(50, limit)
    }
    headers = {"User-Agent": USER_AGENT}

    files = []
    total_fetched = 0
    api_calls = 0

    while total_fetched < limit:
        api_calls += 1
        start_time = time.time()
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        end_time = time.time()
        print(f"API call {api_calls} took {end_time - start_time:.2f} seconds")
        
        data = response.json()

        if "query" not in data or "categorymembers" not in data["query"]:
            print(f"Error in API response: {data}")
            break

        batch = [item["title"] for item in data["query"]["categorymembers"]]
        if license_types != ["any"]:
            batch = check_licenses_batch(batch, license_types)

        files.extend(batch[:limit - total_fetched])
        total_fetched += len(batch)

        print(f"Total files found so far: {total_fetched}")

        if "continue" in data and total_fetched < limit:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
        else:
            break

    return files[:limit]

def check_licenses_batch(file_titles, license_types):
    base_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "prop": "imageinfo",
        "iiprop": "extmetadata",
        "titles": "|".join(file_titles)
    }
    headers = {"User-Agent": USER_AGENT}
    
    start_time = time.time()
    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e}")
            print(f"Response content: {response.text[:1000]}...")
            return []
        
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return []

    end_time = time.time()
    print(f"Batch license check for {len(file_titles)} files took {end_time - start_time:.2f} seconds")

    valid_files = []
    if "query" in data and "pages" in data["query"]:
        for page in data["query"]["pages"].values():
            if "imageinfo" in page and "extmetadata" in page["imageinfo"][0]:
                metadata = page["imageinfo"][0]["extmetadata"]
                if "LicenseShortName" in metadata:
                    license_short_name = metadata["LicenseShortName"]["value"]
                    if any(normalize_string(lt) in normalize_string(license_short_name) for lt in license_types):
                        valid_files.append(page["title"])

    return valid_files

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
