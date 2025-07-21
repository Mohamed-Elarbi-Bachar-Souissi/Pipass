# pypi_fetcher.py
# This module is responsible for fetching (downloading) Python packages
# from PyPI using Playwright, bypassing typical network restrictions.

import os
import re
from playwright.sync_api import sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# --- Configuration for bundled browsers ---
# This assumes the 'playwright_browsers' folder is directly next to the main script
# (which will be pipass.py, but this path is relative to where this module is run
# or where the main script sets the environment variable).
# For a truly portable solution, the main pipass.py script will set this
# environment variable once before importing and using this module.
# However, for standalone testing of pypi_fetcher, we'll keep it here for now.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUNDLED_BROWSERS_PATH = os.path.join(BASE_DIR, "playwright_browsers")

# Set the environment variable so Playwright knows where to find the browsers.
# This must be done BEFORE sync_playwright() is called.
# In the final Pipass structure, the main pipass.py will ensure this is set.
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BUNDLED_BROWSERS_PATH
# --- End Configuration ---

def download_package_with_playwright(package_name: str, download_dir: str = "downloads") -> str | None:
    """
    Downloads the latest .whl file for a given package from PyPI using Playwright.

    Args:
        package_name (str): The name of the Python package to download (e.g., "requests").
        download_dir (str): The subdirectory where the downloaded file will be saved.
                            Defaults to "downloads".

    Returns:
        str | None: The full path to the downloaded .whl file if successful,
                    otherwise None.
    """
    # Ensure download directory exists relative to the script's execution
    # For a portable app, this will be relative to the main pipass.py location
    full_download_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), download_dir)
    os.makedirs(full_download_path, exist_ok=True)

    print(f"Downloads will be saved to: {full_download_path}")

    downloaded_file_path = None

    with sync_playwright() as p:
        # Launch a headless Firefox browser. Can switch to p.chromium.launch() if preferred.
        browser = p.firefox.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        print(f"Navigating to PyPI for {package_name}...")
        project_url = f"https://pypi.org/project/{package_name}/#files"
        
        try:
            # Navigate to the package's PyPI page, with a generous timeout
            page.goto(project_url, timeout=60000)
            print("Page loaded. Looking for download links...")

            # Locate the .whl download link using a robust CSS selector and regex for text content.
            # This targets an <a> tag within the section with id "files",
            # whose 'download' attribute ends with ".whl" (preferring .whl files)
            # or whose text content ends with ".whl"
            download_link_locator = page.locator(f'section#files a[download$=".whl"]').first
            
            # If the direct download attribute locator doesn't work, try by text content
            if not download_link_locator.is_visible():
                download_link_locator = page.get_by_role("link", name=re.compile(r"\.whl$")).first

            try:
                # Explicitly wait for the locator to be visible with an increased timeout
                download_link_locator.wait_for(state='visible', timeout=30000) # Increased timeout to 30 seconds
                
                # Get the suggested filename from the 'download' attribute or from the href
                file_name_attr = download_link_locator.get_attribute('download')
                if not file_name_attr: # Fallback if 'download' attribute is missing
                     file_name_attr = os.path.basename(download_link_locator.get_attribute('href').split('?')[0])

                print(f"Found potential download link for: {file_name_attr}. Clicking...")
                
                # Expect the download to start and get the download object
                with page.expect_download() as download_info:
                    download_link_locator.click()

                download = download_info.value
                
                final_downloaded_path = os.path.join(full_download_path, download.suggested_filename)
                
                print(f"Downloading {download.suggested_filename} to {final_downloaded_path}...")
                download.save_as(final_downloaded_path)
                print(f"Download complete: {download.suggested_filename}")
                downloaded_file_path = final_downloaded_path

            except PlaywrightTimeoutError:
                print(f"Could not find a .whl download link for {package_name} on the page within the timeout.")
                print("This might indicate the package version is old, or the page structure changed, or network issue after page load.")
                page.screenshot(path=os.path.join(full_download_path, f"debug_pypi_page_{package_name}.png")) # Save screenshot for debugging
                print(f"Screenshot saved to {os.path.join(full_download_path, f'debug_pypi_page_{package_name}.png')}")

        except Exception as e:
            print(f"An unexpected error occurred during navigation or download for {package_name}: {e}")
            page.screenshot(path=os.path.join(full_download_path, f"error_pypi_page_{package_name}.png"))
            print(f"Screenshot saved to {os.path.join(full_download_path, f'error_pypi_page_{package_name}.png')}")

        finally:
            browser.close()
            print("Browser closed.")
    
    return downloaded_file_path

# This __name__ == "__main__" block is for testing pypi_fetcher.py in isolation.
# In the final Pipass project, pipass.py will be the main entry point.
if __name__ == "__main__":
    print("--- Testing pypi_fetcher.py in isolation ---")
    # You can test a package download here
    test_package = "requests"
    downloaded_path = download_package_with_playwright(test_package)
    if downloaded_path:
        print(f"Successfully downloaded: {downloaded_path}")
    else:
        print(f"Failed to download {test_package}.")
    print("------------------------------------------")
