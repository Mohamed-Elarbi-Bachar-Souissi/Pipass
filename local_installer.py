# local_installer.py
# This module handles the local installation of packages using pip,
# specifically designed for an iterative process that resolves dependencies
# by requesting them from pypi_fetcher if missing.

import subprocess
import re
import os
import zipfile
import shutil
import sys # <--- ADD THIS LINE
from typing import List, Set, Tuple, Callable

# Define a type hint for the fetcher function
# It takes package_name and download_dir, and returns the path to the downloaded file or None
FetcherFunc = Callable[[str, str], str | None]

def extract_dependencies_from_whl(whl_path: str) -> Set[str]:
    """
    Extracts package dependencies from the METADATA file within a .whl archive.

    Args:
        whl_path (str): The path to the .whl file.

    Returns:
        Set[str]: A set of dependency names (e.g., {"requests", "urllib3"}).
                  Returns an empty set if no dependencies are found or an error occurs.
    """
    dependencies = set()
    temp_extract_dir = None
    try:
        # Create a temporary directory to extract the wheel
        temp_extract_dir = f"{whl_path}_extracted_temp"
        os.makedirs(temp_extract_dir, exist_ok=True)

        with zipfile.ZipFile(whl_path, 'r') as zip_ref:
            # Look for METADATA file (e.g., requests-2.32.4.dist-info/METADATA)
            # The exact path can vary, so we search for it.
            metadata_file_name = None
            for name in zip_ref.namelist():
                if name.endswith('.dist-info/METADATA'):
                    metadata_file_name = name
                    break

            if metadata_file_name:
                zip_ref.extract(metadata_file_name, temp_extract_dir)
                metadata_path = os.path.join(temp_extract_dir, metadata_file_name)

                with open(metadata_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('Requires-Dist:'):
                            # Example: Requires-Dist: charset-normalizer (>=2.0.0,<4)
                            # We only care about the package name
                            match = re.match(r'Requires-Dist:\s*([a-zA-Z0-9._-]+)', line)
                            if match:
                                dep_name = match.group(1).strip()
                                dependencies.add(dep_name)
            else:
                print(f"Warning: METADATA file not found in {whl_path}")

    except Exception as e:
        print(f"Error extracting dependencies from {whl_path}: {e}")
    finally:
        if temp_extract_dir and os.path.exists(temp_extract_dir):
            shutil.rmtree(temp_extract_dir) # Clean up temporary directory
    return dependencies


def parse_pip_error_for_missing_deps(error_output: str) -> Set[str]:
    """
    Parses pip's error output to identify missing package dependencies.

    Args:
        error_output (str): The stderr output from a failed pip install command.

    Returns:
        Set[str]: A set of package names that pip reported as missing.
    """
    missing_deps = set()
    # Common patterns for missing dependencies in pip output
    # Example: "No matching distribution found for some-package"
    # Example: "ERROR: Could not find a version that satisfies the requirement some-package"
    # Example: "The following packages are not available: some-package"
    
    # Pattern 1: No matching distribution found for <package_name>
    pattern1 = re.compile(r"No matching distribution found for ([a-zA-Z0-9._-]+)")
    # Pattern 2: Could not find a version that satisfies the requirement <package_name>
    pattern2 = re.compile(r"Could not find a version that satisfies the requirement ([a-zA-Z0-9._-]+)")
    # Pattern 3: (less common for direct missing, more for version conflicts)
    # "The conflict is caused by:" or "Requires <package_name>"
    
    for line in error_output.splitlines():
        match1 = pattern1.search(line)
        if match1:
            missing_deps.add(match1.group(1).strip())
            continue
        
        match2 = pattern2.search(line)
        if match2:
            missing_deps.add(match2.group(1).strip())
            continue
            
        # Add more patterns if specific error messages are consistently observed
        # For example, if it explicitly lists "missing dependencies: X, Y, Z"
        # For now, these two are the most common for "not found".

    return missing_deps

def install_packages_locally(
    main_package_name: str,
    download_dir: str,
    fetch_func: FetcherFunc,
    max_retries: int = 5
) -> bool:
    """
    Attempts to install packages locally using pip, iteratively downloading
    missing dependencies.

    Args:
        main_package_name (str): The name of the primary package to install.
        download_dir (str): The directory where .whl files are stored and will be searched.
        fetch_func (FetcherFunc): A callable function (from pypi_fetcher) to download a package.
                                  Expected signature: fetch_func(package_name: str, download_dir: str) -> str | None
        max_retries (int): Maximum number of installation attempts.

    Returns:
        bool: True if the main package and its dependencies are successfully installed,
              False otherwise.
    """
    installed_successfully = False
    attempt = 0
    downloaded_packages: Set[str] = set() # Keep track of packages we've already tried to download

    # Initial download of the main package
    print(f"\n--- Attempting to download main package: {main_package_name} ---")
    main_package_path = fetch_func(main_package_name, download_dir)
    if not main_package_path:
        print(f"Error: Could not download the main package '{main_package_name}'. Aborting installation.")
        return False
    
    # Add the main package to the list of available local packages
    downloaded_packages.add(main_package_name)

    # Extract initial dependencies from the main package's wheel
    initial_deps = extract_dependencies_from_whl(main_package_path)
    print(f"Initial dependencies identified for {main_package_name}: {initial_deps}")
    
    # Download these initial dependencies
    for dep in initial_deps:
        if dep not in downloaded_packages:
            print(f"Attempting to download initial dependency: {dep}")
            dep_path = fetch_func(dep, download_dir)
            if dep_path:
                downloaded_packages.add(dep)
            else:
                print(f"Warning: Could not download initial dependency '{dep}'. It might be resolved later or cause an error.")

    while not installed_successfully and attempt < max_retries:
        attempt += 1
        print(f"\n--- Installation Attempt {attempt}/{max_retries} for {main_package_name} ---")

        # Construct the pip install command
        # We need to include all downloaded packages in --find-links
        # and explicitly list the main package and any *known* dependencies
        # that pip might not resolve automatically from the local index.
        # However, pip's --find-links works by creating a simple index.
        # So, we just need to tell it where to look.
        
        command = [
            sys.executable, "-m", "pip", "install",
            "--no-index", # Do not use PyPI's main index
            "--find-links", download_dir, # Look for packages in our local download directory
            main_package_name
        ]
        
        print(f"Running command: {' '.join(command)}")

        try:
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False # Do not raise an exception for non-zero exit codes
            )

            if process.returncode == 0:
                print(f"Successfully installed {main_package_name} and its dependencies!")
                print("Pip Output:\n", process.stdout)
                installed_successfully = True
            else:
                print(f"Installation failed for {main_package_name}. Pip Exit Code: {process.returncode}")
                print("Pip Stdout:\n", process.stdout)
                print("Pip Stderr:\n", process.stderr)

                missing_deps = parse_pip_error_for_missing_deps(process.stderr)
                if not missing_deps:
                    # If pip failed but we couldn't parse specific missing deps,
                    # it might be a different error or a complex dependency conflict.
                    print("Could not identify specific missing dependencies from pip output. "
                          "Reviewing pip's stderr for clues.")
                    break # Exit loop if we can't make progress
                
                newly_identified_deps = missing_deps - downloaded_packages
                if not newly_identified_deps:
                    print("No new missing dependencies identified. "
                          "This might indicate a version conflict or other installation issue not related to missing files.")
                    break # Exit loop if no new deps to download

                print(f"Identified missing dependencies: {newly_identified_deps}")
                
                # Download the newly identified missing dependencies
                download_success_count = 0
                for dep in newly_identified_deps:
                    print(f"Attempting to download missing dependency: {dep}")
                    dep_path = fetch_func(dep, download_dir)
                    if dep_path:
                        downloaded_packages.add(dep)
                        download_success_count += 1
                    else:
                        print(f"Warning: Failed to download '{dep}'. This might prevent successful installation.")
                
                if download_success_count == 0 and len(newly_identified_deps) > 0:
                    print("Failed to download any of the newly identified missing dependencies. Aborting further retries.")
                    break # No progress on downloading, so stop

        except FileNotFoundError:
            print(f"Error: Python or pip command not found. Ensure Python and pip are correctly set up in your virtual environment.")
            break
        except Exception as e:
            print(f"An unexpected error occurred during pip installation: {e}")
            break

    return installed_successfully

# This __name__ == "__main__" block is for testing local_installer.py in isolation.
# In the final Pipass project, pipass.py will be the main entry point.
if __name__ == "__main__":
    print("--- Testing local_installer.py in isolation (requires pypi_fetcher.py in same directory) ---")
    # Mock a fetcher function for testing purposes if pypi_fetcher.py is not fully integrated yet
    # For actual testing, you'd import download_package_with_playwright from pypi_fetcher
    
    # You would typically import this:
    from pypi_fetcher import download_package_with_playwright as mock_fetcher_func

    test_package_to_install = "pylint" # Example package
    test_download_dir = "test_downloads"
    
    # Ensure the test_downloads directory is clean
    if os.path.exists(test_download_dir):
        shutil.rmtree(test_download_dir)
    os.makedirs(test_download_dir, exist_ok=True)

    print(f"Attempting to install {test_package_to_install} locally...")
    success = install_packages_locally(
        main_package_name=test_package_to_install,
        download_dir=test_download_dir,
        fetch_func=mock_fetcher_func # Pass the actual fetcher function
    )

    if success:
        print(f"\nInstallation of {test_package_to_install} completed successfully!")
    else:
        print(f"\nInstallation of {test_package_to_install} failed after multiple attempts.")
    
    # Clean up test_downloads after testing
    # if os.path.exists(test_download_dir):
    #     shutil.rmtree(test_download_dir)
    print("------------------------------------------")
