export function normalizeFishReference(value: string): string {
  const reference = value.trim();
  if (reference.includes("://") || /^(www\.)?fish\.audio\//i.test(reference)) {
    try {
      const url = new URL(reference.includes("://") ? reference : `https://${reference}`);
      const match = url.pathname.match(/^\/app\/m\/([a-f\d]{32})\/?$/i);
      if (!["http:", "https:"].includes(url.protocol) || !["fish.audio", "www.fish.audio"].includes(url.host)
        || url.username || url.password || !match) throw new Error();
      return match[1].toLowerCase();
    } catch {
      throw new Error("Enter a reference ID or a Fish Audio voice URL such as https://fish.audio/app/m/<reference-id>/.");
    }
  }
  return /^[a-f\d]{32}$/i.test(reference) ? reference.toLowerCase() : reference;
}

export function fishVoicePageUrl(reference: string): string | null {
  try {
    const id = normalizeFishReference(reference);
    return /^[a-f\d]{32}$/i.test(id) ? `https://fish.audio/app/m/${id}/` : null;
  } catch {
    return null;
  }
}
