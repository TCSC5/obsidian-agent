import os, requests, json

class OpenAIError(Exception): pass

def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)

def chat(messages, model=None, temperature=0.2, max_tokens=1200):
    """
    Lightweight wrapper around OpenAI Chat Completions API via requests.

    Reads environment variables at CALL TIME to avoid stale values:
      - OPENAI_API_KEY (required)
      - OPENAI_BASE_URL (optional, default https://api.openai.com/v1)
      - OPENAI_MODEL (optional, default gpt-4o-mini)
    """
    api_key = _get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OpenAIError("OPENAI_API_KEY missing in environment")

    base = _get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    mdl = model or _get("OPENAI_MODEL", "gpt-4o-mini")

    url = base + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": mdl,
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "messages": messages
    }
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    if resp.status_code >= 400:
        raise OpenAIError(f"OpenAI API error {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        raise OpenAIError(f"Unexpected API response: {data}")
