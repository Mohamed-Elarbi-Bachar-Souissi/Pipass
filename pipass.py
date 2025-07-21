# pipass.py
# This is the main entry point for the Pipass project.
# It orchestrates the process of fetching Python packages and their dependencies
# from PyPI (bypassing proxies using Playwright) and then installing them locally.

import sys
import os
import shutil

# Import the core functionalities from our modules
from pypi_fetcher import download_package_with_playwright
from local_installer import install_packages_locally

# --- Global Configuration ---
# Define the base directory for the entire Pipass project.
# This is crucial for portability, as all other paths are relative to this.
# This script is expected to be in the root of the Pipass_Portable folder.
PIP_ASS_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define the directory where downloaded .whl files will be stored.
DOWNLOADS_DIR = os.path.join(PIP_ASS_BASE_DIR, "downloads")

# Define the directory where Playwright browser binaries are located.
# This environment variable must be set before Playwright is used.
# pypi_fetcher.py already sets this internally, but it's good practice
# to ensure it's set at the highest level if other modules might use Playwright.
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(PIP_ASS_BASE_DIR, "playwright_browsers")
# --- End Global Configuration ---

def main():
    """
    Main function to parse arguments and start the Pipass package installation process.
    """
    print("--- Welcome to Pipass: Portable Python Package Installer ---")
    print(f"Pipass Base Directory: {PIP_ASS_BASE_DIR}")
    print(f"Downloads will be stored in: {DOWNLOADS_DIR}")

    # Ensure the downloads directory exists
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    if len(sys.argv) < 2:
        print("\nUsage: python pipass.py <package_name>")
        print("Example: python pipass.py requests")
        print("Example: python pipass.py pylint")
        print("\nTo clean up downloaded files: python pipass.py --clean")
        sys.exit(1)

    command = sys.argv[1]

    if command == "--clean":
        print(f"\n--- Cleaning up downloads directory: {DOWNLOADS_DIR} ---")
        if os.path.exists(DOWNLOADS_DIR):
            try:
                shutil.rmtree(DOWNLOADS_DIR)
                print("Downloads directory cleaned successfully.")
            except Exception as e:
                print(f"Error cleaning downloads directory: {e}")
        else:
            print("Downloads directory does not exist. Nothing to clean.")
        sys.exit(0)
    
    package_to_install = command # The first argument is the package name

    print(f"\n--- Starting installation process for: {package_to_install} ---")
    
    # Call the local_installer to handle the iterative installation
    success = install_packages_locally(
        main_package_name=package_to_install,
        download_dir=DOWNLOADS_DIR,
        fetch_func=download_package_with_playwright # Pass the pypi_fetcher's download function
    )

    if success:
        print(f"\n--- Pipass: Successfully installed {package_to_install} and its dependencies! ---")
    else:
        print(f"\n--- Pipass: Failed to install {package_to_install} after multiple attempts. ---")
        print("Please check the logs and screenshots in the downloads directory for more details.")

if __name__ == "__main__":
    main()
