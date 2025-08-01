#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import requests
import time
from dataclasses import dataclass
from pathlib import Path
from src.onemcp.util.env import ONEMCP_SRC_ROOT
from tqdm import tqdm
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class ProcessResult:
    index: int
    repository_url: Optional[str]
    ok: bool
    error: Optional[str] = None
    data: Optional[Any] = None  # whatever your pipeline returns


def load_entries(json_path: str | Path) -> List[Dict[str, Any]]:
    """
    Load the JSON file containing a list of entries into memory.
    """
    p = Path(json_path)
    with p.open("r", encoding="utf-8") as fh:
        entries = json.load(fh)

    if not isinstance(entries, list):
        raise ValueError("Top-level JSON must be a list of entries.")

    return entries


def process_all(
    entries: List[Dict[str, Any]],
    process_fn: Callable[[Dict[str, Any]], Any],
    progress: bool = True,
    show_every: int = 100,  # used by fallback progress only
) -> Tuple[List[ProcessResult], Dict[str, Any]]:
    """
    Run `process_fn` on each entry and track progress, successes, and failures.

    Returns:
        (results, summary) where:
          - results: list of ProcessResult (one per entry)
          - summary: dict with counts and elapsed seconds
    """
    total = len(entries)
    results: List[ProcessResult] = []
    ok_count = 0
    fail_count = 0
    start_time = time.time()

    # Choose progress strategy
    if progress and tqdm is not None:
        bar = tqdm(total=total, unit="entry", dynamic_ncols=True)
        update_bar = lambda: bar.set_postfix(ok=ok_count, fail=fail_count, refresh=False)
    else:
        bar = None
        last_shown = -1

        def update_bar() -> None:
            nonlocal last_shown
            processed = ok_count + fail_count
            if processed != last_shown and (processed % show_every == 0 or processed == total):
                last_shown = processed
                print(f"Processed {processed}/{total}  (ok={ok_count}, fail={fail_count})")

    try:
        for i, entry in enumerate(entries):
            repo = entry.get("repository_url")
            try:
                data = process_fn(entry)  # <-- your custom pipeline
                results.append(ProcessResult(index=i, repository_url=repo, ok=True, data=data))
                ok_count += 1
            except Exception as e:
                results.append(
                    ProcessResult(index=i, repository_url=repo, ok=False, error=str(e))
                )
                fail_count += 1

            if bar is not None:
                bar.update(1)
                bar.set_postfix(ok=ok_count, fail=fail_count, refresh=False)
            else:
                update_bar()
    finally:
        if bar is not None:
            bar.close()

    elapsed = time.time() - start_time
    summary = {
        "total": total,
        "ok": ok_count,
        "failed": fail_count,
        "elapsed_seconds": round(elapsed, 3),
        "success_rate": (ok_count / total) if total else 0.0,
    }
    return results, summary


if __name__ == "__main__":
    """
    Main script to populate the MCP database from a list of existing MCP
    servers.

    In the future, this method should be run as a standalone, daemon process
    that mines the internet looking for new MCP servers.
    """
    json_path = os.path.join(
        ONEMCP_SRC_ROOT,
        "discovery",
        "github_extraction",
        "awesome_mcp_servers",
        "awesome_mcp_servers.json"
    )
    entries = load_entries(json_path)

    sandbox_http_host = "http://localhost"
    sandbox_http_port = "8080"

    print("Processing {len(entries)} entries...")

    def process_entry(entry: Dict[str, Any]) -> Any:
        """
        Do whatever processing you need for each entry.
        Return any data you want to keep.
        Raise an exception to mark this entry as failed.
        """
        # Example: pretend to succeed if there's a README; fail otherwise
        readme_content = entry.get("readme_content", "")
        if len(readme_content) == 0:
            raise RuntimeError("Missing readme_content")

        repository_url = entry.get("repository_url", "")
        if len(repository_url) == 0:
            raise RuntimeError("Missing readme_content")

        language = entry.get("language", "")
        if language.lower() != "python":
            raise RuntimeError("MCP not written in Python")

        url = "http://localhost:8080/sandbox"
        headers = {
            "Content-Type": "application/json",
            "X-OneMCP-Message-Type": "DISCOVER",
        }
        payload = {
            "repository_url": repository_url,
            "repository_readme": readme_content,
        }

        response = requests.post(url, headers=headers, json=payload).json()

        result = {
            "name": entry.get("name"),
            "description": entry.get("description"),
            "tools": response.get("tools"),
            "setup_script": response.get("setup_script"),
        }
        print(result)

        # TODO: post to the database

        return result

    results, summary = process_all(entries, process_entry, progress=True)

    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))

    # Optional: show a few failures for debugging
    failed = [r for r in results if not r.ok]
    if failed:
        print("\nFirst few failures:")
        for r in failed[:5]:
            print(f"  idx={r.index} url={r.repository_url} error={r.error}")
