import re
from urllib.parse import urlsplit


def normalize_fish_reference(value: str) -> str:
    reference = value.strip()
    if "://" in reference or reference.lower().startswith(("fish.audio/", "www.fish.audio/")):
        url = urlsplit(reference if "://" in reference else f"https://{reference}")
        match = re.fullmatch(r"/app/m/([a-fA-F0-9]{32})/?", url.path)
        if url.scheme not in {"http", "https"} or url.netloc.lower() not in {"fish.audio", "www.fish.audio"} or not match:
            raise ValueError("Enter a reference ID or a Fish Audio voice URL such as https://fish.audio/app/m/<reference-id>/.")
        return match.group(1).lower()
    return reference.lower() if re.fullmatch(r"[a-fA-F0-9]{32}", reference) else reference
