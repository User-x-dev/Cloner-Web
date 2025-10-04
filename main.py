# python main.py
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
import re
import queue
import time
from concurrent.futures import ThreadPoolExecutor

MAX_THREADS = 5
REQUEST_DELAY = 0.5
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

def create_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

def sanitize_filename(filename):
    return re.sub(r'[^\w\-_\. ]', '_', filename)

def normalize_url(url):
    url, _ = urldefrag(url)
    return url.rstrip('/')

def is_valid_url(url, base_domain):
    try:
        parsed = urlparse(url)
        return parsed.netloc == base_domain and parsed.scheme in ('http', 'https')
    except:
        return False

def download_resource(url, folder, session):
    try:
        headers = {'User-Agent': USER_AGENT}
        response = session.get(url, headers=headers, stream=True, timeout=10)
        if response.status_code == 200:
            parsed_url = urlparse(url)
            filename = sanitize_filename(os.path.basename(parsed_url.path))
            if not filename:
                filename = 'index.html'
            elif not os.path.splitext(filename)[1]:
                ext = response.headers.get('content-type', '').split('/')[-1]
                filename += f'.{ext}' if ext in ['css', 'js', 'jpg', 'jpeg', 'png', 'gif', 'woff', 'woff2', 'ttf', 'mp4', 'webm'] else '.html'
            file_path = os.path.join(folder, filename)
            create_directory(os.path.dirname(file_path))
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return filename
        return None
    except Exception:
        return None

def rewrite_links(soup, base_url, base_folder):
    base_domain = urlparse(base_url).netloc
    for tag in soup.find_all(['a', 'img', 'link', 'script', 'source', 'video']):
        if tag.name == 'a' and tag.get('href'):
            href = urljoin(base_url, tag['href'])
            if is_valid_url(href, base_domain):
                parsed_href = urlparse(href)
                local_path = os.path.join(base_folder, sanitize_filename(parsed_href.path.lstrip('/') or 'index.html'))
                tag['href'] = os.path.relpath(local_path, start=os.path.dirname(local_path))
        elif tag.name == 'img' and tag.get('src'):
            tag['src'] = os.path.basename(urlparse(tag['src']).path)
        elif tag.name == 'link' and tag.get('href'):
            tag['href'] = os.path.basename(urlparse(tag['href']).path)
        elif tag.name == 'script' and tag.get('src'):
            tag['src'] = os.path.basename(urlparse(tag['src']).path)
        elif tag.name == 'source' and tag.get('src'):
            tag['src'] = os.path.basename(urlparse(tag['src']).path)
        elif tag.name == 'video' and tag.get('src'):
            tag['src'] = os.path.basename(urlparse(tag['src']).path)

def clone_page(url, output_dir, base_url, visited, session):
    normalized_url = normalize_url(url)
    if normalized_url in visited:
        return
    visited.add(normalized_url)
    try:
        headers = {'User-Agent': USER_AGENT}
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return
        content_type = response.headers.get('content-type', '')
        if 'text/html' not in content_type:
            return
        soup = BeautifulSoup(response.text, 'html.parser')
        parsed_url = urlparse(url)
        base_domain = parsed_url.netloc
        base_folder = os.path.join(output_dir, sanitize_filename(base_domain))
        create_directory(base_folder)
        path = parsed_url.path.lstrip('/')
        if not path:
            path = 'index.html'
        elif not os.path.splitext(path)[1]:
            path += '/index.html'
        file_path = os.path.join(base_folder, sanitize_filename(path))
        create_directory(os.path.dirname(file_path))
        resources = []
        for tag in soup.find_all(['img', 'link', 'script', 'source', 'video', 'font']):
            if tag.name == 'img' and tag.get('src'):
                resources.append(tag['src'])
            elif tag.name == 'link' and tag.get('href'):
                resources.append(tag['href'])
            elif tag.name == 'script' and tag.get('src'):
                resources.append(tag['src'])
            elif tag.name == 'source' and tag.get('src'):
                resources.append(tag['src'])
            elif tag.name == 'video' and tag.get('src'):
                resources.append(tag['src'])
        for resource in resources:
            resource_url = urljoin(url, resource)
            if is_valid_url(resource_url, base_domain):
                download_resource(resource_url, base_folder, session)
        rewrite_links(soup, base_url, base_folder)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        for link in soup.find_all('a', href=True):
            href = urljoin(url, link['href'])
            if is_valid_url(href, base_domain) and normalize_url(href) not in visited:
                url_queue.put(href)
    except Exception:
        pass

def worker(output_dir, base_url, visited, session):
    while not url_queue.empty():
        try:
            url = url_queue.get_nowait()
            clone_page(url, output_dir, base_url, visited, session)
            time.sleep(REQUEST_DELAY)
        except queue.Empty:
            break
        except Exception:
            pass
        finally:
            url_queue.task_done()

def clone_website(url, output_dir):
    try:
        create_directory(output_dir)
        visited = set()
        global url_queue
        url_queue = queue.Queue()
        url_queue.put(url)
        with requests.Session() as session:
            with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
                futures = []
                for _ in range(MAX_THREADS):
                    future = executor.submit(worker, output_dir, url, visited, session)
                    futures.append(future)
                for future in futures:
                    future.result()
                url_queue.join()
    except Exception:
        pass

def main():
    url = input("Enter the website URL to clone (e.g., https://example.com): ").strip()
    output_dir = "cloned_websites"
    clone_website(url, output_dir)

if __name__ == "__main__":
    main()