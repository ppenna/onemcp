import json
import os
from urllib.parse import urlparse

import markdown
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from tqdm import tqdm
from typing import Any, List

# Load .env file
load_dotenv()

github_access_token = os.environ["GITHUB_TOKEN"]

# COMMON ACROSS CALLS
BASE_GITHUB_API_URL = "https://api.github.com"
HEADERS = {
    "Authorization": f"token {github_access_token}",
    "Accept": "application/vnd.github+json",
}


class BaseGitHubRepoExplorer:
    def __init__(self, repo_url: str):
        # Parse the URL
        parsed = urlparse(repo_url)

        # Extract only the path
        clean_path = parsed.path
        # print(clean_path)

        self.repo_url = repo_url
        # Extract owner and repo
        params = clean_path.split("/")
        # Second and third should always be owner/repo
        self.owner = params[1]
        # Some repo urls come with .git at
        self.repo = params[2].replace(".git", "")
        # Get information
        self.repo_information = self.get_repo_information(
            owner=self.owner, repo=self.repo
        )
        self.default_branch = self.repo_information["default_branch"]
        # Extract readme content and title
        self.readme_content = self.get_repo_readme()

        self.programming_languages = self.get_repo_programming_languages(
            self.repo_information["languages_url"]
        )

    # Function to get repo information
    def get_repo_information(self, owner: str, repo: str) -> Any:
        endpoint = f"/repos/{owner}/{repo}"
        repo_url = f"{BASE_GITHUB_API_URL}{endpoint}"
        response = requests.get(repo_url, headers=HEADERS)
        return response.json()

    # Function to get programming languages
    def get_repo_programming_languages(self, language_url: str) -> Any:
        response = requests.get(language_url, headers=HEADERS)
        response.raise_for_status()
        return response.json()

    def get_repo_readme(self) -> str:
        self.readme_title = ""

        base_readme_url = f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/refs/heads/{self.default_branch}"
        name_variations = ["README.md", "readme.md", "Readme.md", "README.rst"]
        folder_variations = ["/", "/.github/", "/docs/"]
        # Try all possible variations
        for fv in folder_variations:
            for nm in name_variations:
                readme_url = f"{base_readme_url}{fv}{nm}"
                try:
                    response = requests.get(readme_url)
                    response.raise_for_status()
                    # If no fail, we have content
                    self.readme_url = readme_url
                    # Try to extract title from readme as well
                    # Convert markdown to HTML
                    html_content = markdown.markdown(response.text)
                    soup = BeautifulSoup(html_content, "html.parser")
                    try:
                        self.readme_title = soup.find(["h1"]).text
                    except Exception:
                        self.readme_title = ""
                        # print(f"Error getting Readme Title: {self.repo_url}")
                    # at this point we should break
                    return response.text

                except Exception:
                    # print(f"not found for: {readme_url} ")
                    continue
        return ""


def get_awesome_mcp_servers_urls(url: str) -> List[str]:
    # Download markdown content
    response = requests.get(url)
    response.raise_for_status()
    md_content = response.text

    # Convert markdown to HTML
    html_content = markdown.markdown(md_content)

    # Parse HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract all raw URLs under <h3> sections
    urls_by_section: dict[str, List[Any]] = {}

    tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol"])

    current_h3 = None
    recording = False

    for tag in tags:
        if tag.name == "h3":
            current_h3 = tag.get_text(strip=True)
            urls_by_section[current_h3] = []
            recording = True
        elif tag.name in ["h1", "h2", "h3"] and recording:
            # End the current section when next h1–h3 is encountered
            recording = False
            current_h3 = None
        elif recording and tag.name in ["ul", "ol"]:
            for li in tag.find_all("li"):
                for a in li.find_all("a", href=True):
                    urls_by_section[current_h3].append(a["href"])

    # Gather results
    results = []
    for _, links in urls_by_section.items():
        for link in links:
            if "https://github.com" in link and link not in results:
                results.append(link)

    return results


def batch_extract_mcp_urls(urls: List[str], saved_results_filename: str) -> None:
    # Pick up where we left
    json_results = []
    if os.path.isfile(saved_results_filename):
        with open(saved_results_filename) as file:
            json_results = json.load(file)
    # Print stats
    json_existing_urls = [x["repository_url"] for x in json_results]
    empty_readme = [x for x in json_results if x["readme_content"] == ""]
    empty_title = [x for x in json_results if x["readme_title"] == ""]
    print(f"Records: {len(json_existing_urls)}/{len(urls)}")
    print(f"Records with no readme titles: {len(empty_title)}")
    print(f"Records with no readmes contents: {len(empty_readme)}")
    completed = len(json_existing_urls)

    for url in tqdm(urls):
        # Skip the ones we have done
        if url in json_existing_urls:
            continue

        url_object = {}
        url_object["repository_url"] = url

        try:
            GitHubExplorer = BaseGitHubRepoExplorer(repo_url=url)

            url_object["name"] = GitHubExplorer.repo_information["name"]
            url_object["description"] = GitHubExplorer.repo_information["description"]
            url_object["language"] = GitHubExplorer.repo_information["language"]
            url_object["all_languages"] = GitHubExplorer.programming_languages
            url_object["readme_url"] = GitHubExplorer.readme_url
            url_object["readme_content"] = GitHubExplorer.readme_content
            url_object["readme_title"] = GitHubExplorer.readme_title

            json_results.append(url_object)
            # Always write
            with open(saved_results_filename, "w") as json_file:
                json.dump(json_results, json_file, indent=4)
            # Counter for completed
            completed += 1
        except Exception as e:
            print(f"Error: {url}")
            print(e)
            continue

    print(f"Finished. Got {completed}/{len(urls)}")
