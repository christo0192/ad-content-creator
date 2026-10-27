"""LLM access via `claude -p` (Claude Code headless, Max plan — no API key).

extract_json(): page/article -> validated dict (Haiku). The tool-call gate is
applied by the caller via the Pydantic model. synthesize(): free-text (Sonnet).

Long prompts (full article text) are piped via STDIN to avoid OS command-line
length limits. Output often comes back wrapped in a ```json fence -> stripped.
"""
from __future__ import annotations
import subprocess, json, re
from concurrent.futures import ThreadPoolExecutor, as_completed
import config as C

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    m = _FENCE.search(t)
    return m.group(1).strip() if m else t


def claude(prompt: str, model: str | None = None, timeout: int | None = None,
           effort: str | None = None) -> str:
    """One headless call. Prompt is sent on STDIN (handles large content)."""
    model = model or C.EXTRACT_MODEL
    timeout = timeout or C.LLM_TIMEOUT_S
    effort = effort or C.EXTRACT_EFFORT
    proc = subprocess.run(
        [C.CLAUDE_BIN, "-p", "--model", model,
         "--effort", effort, "--output-format", "text"],
        input=prompt, capture_output=True, text=True, encoding="utf-8",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p ({model}) exit {proc.returncode}: "
                           f"{(proc.stderr or '')[:300]}")
    return (proc.stdout or "").strip()


def extract_json(prompt: str, model: str | None = None, retries: int = 2,
                 timeout: int | None = None, effort: str | None = None):
    """Call claude and parse a JSON object/array from the reply. Retries on
    unparseable output (appending a stricter nudge). Defaults to the extraction
    tier (Haiku, low effort)."""
    last = None
    p = prompt
    for attempt in range(retries + 1):
        out = claude(p, model=model, timeout=timeout, effort=effort or C.EXTRACT_EFFORT)
        try:
            return json.loads(_strip_fences(out))
        except Exception as e:
            last = e
            p = prompt + "\n\nReturn ONLY valid JSON. No prose, no markdown fences."
    raise ValueError(f"unparseable JSON after {retries + 1} tries: {last}")


def synthesize(prompt: str, model: str | None = None, timeout: int | None = None,
               effort: str | None = None) -> str:
    """Cross-dataset synthesis tier (Sonnet 5, medium effort by default)."""
    return claude(prompt, model=model or C.SYNTH_MODEL, timeout=timeout,
                  effort=effort or C.SYNTH_EFFORT)


def map_extract(prompts: list[str], model: str | None = None,
                max_workers: int | None = None, timeout: int | None = None) -> list:
    """Run extract_json over many prompts concurrently (bounded). Failures ->
    None in the corresponding slot (caller filters)."""
    workers = max_workers or C.LLM_MAX_CONCURRENCY
    results: list = [None] * len(prompts)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(extract_json, p, model, 2, timeout): i for i, p in enumerate(prompts)}
        for f in as_completed(futs):
            i = futs[f]
            try:
                results[i] = f.result()
            except Exception:
                results[i] = None
    return results
