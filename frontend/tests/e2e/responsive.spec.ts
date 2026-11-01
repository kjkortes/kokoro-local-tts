import {expect, test} from "@playwright/test";


const config = {
  languages: [{code: "a", name: "American English", locale: "en-US"}],
  voices: [
    {id: "af_heart", name: "Heart", language: "a", gender: "female"},
    {id: "am_adam", name: "Adam", language: "a", gender: "male"},
  ],
  presets: [
    {id: "neutral", name: "Neutral", description: "Natural timing with no tonal processing.", speed: 1, pitch: 0, tempo: 1, pause_scale: 1},
    {id: "calm", name: "Calm", description: "Measured delivery with softer pitch and longer pauses.", speed: .9, pitch: -.7, tempo: .94, pause_scale: 1.25},
  ],
  formats: ["wav", "mp3", "flac", "ogg"],
  defaults: {
    engine: "kokoro",
    fish_voice: "b0204e37cbc94a16954c78697b844af2",
    language: "a",
    voice: "af_heart",
    preset: "neutral",
    format: "wav",
  },
  limits: {speed: {min: .5, max: 2}, pitch: {min: -4, max: 4}, tempo: {min: .75, max: 1.25}, pause_scale: {min: .5, max: 2}, volume: {min: 0, max: 1.5}, pause_ms: {min: 0, max: 5000}},
};

async function mockLocalApi(page: import("@playwright/test").Page) {
  const voices = [
    {id: "starter", name: "Original Fish voice", description: "Original narrator", reference_id: "b0204e37cbc94a16954c78697b844af2"},
    ...Array.from({length: 11}, (_, i) => ({id: `voice-${i + 1}`, name: `Voice ${String(i + 1).padStart(2, "0")}`, description: `Narration style ${i + 1}`, reference_id: `reference-${i + 1}`})),
  ];
  await page.route("**/api/config", (route) => route.fulfill({json: config}));
  await page.route("**/api/status", (route) => route.fulfill({json: {state: "ready", device: "cpu", version: "0.1.0", detail: null}}));
  await page.route("**/api/fish-voices", (route) => route.fulfill({json: voices}));
  await page.route("**/api/fish-voices/page?*", (route) => {
    const current = Number(new URL(route.request().url()).searchParams.get("page"));
    return route.fulfill({json: {items: voices.slice((current - 1) * 10, current * 10), total: voices.length, page: current, page_size: 10}});
  });
}

for (const viewport of [{width: 375, height: 812}, {width: 1440, height: 900}]) {
  test(`workspace fits ${viewport.width}px without horizontal overflow`, async ({page}) => {
    await page.setViewportSize(viewport);
    await mockLocalApi(page);
    await page.goto("/");
    await expect(page.getByRole("heading", {name: "Give the words a voice."})).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    expect(overflow).toBe(false);
    await expect(page.getByRole("textbox", {name: "Script", exact: true})).toBeVisible();
    await expect(page.getByRole("button", {name: "Generate speech"})).toBeDisabled();
  });

  test(`Fish voice controls fit ${viewport.width}px with the editor open`, async ({page}) => {
    await page.setViewportSize(viewport);
    await mockLocalApi(page);
    await page.goto("/");
    await page.getByRole("radio", {name: "Fish Audio S2.1 Pro Free — OpenRouter"}).check();
    await expect(page.getByRole("combobox", {name: "Fish voice"})).toHaveValue("starter");
    await expect(page.getByLabel("Timestamp engine")).toHaveValue("whisperx");
    await page.getByLabel("Timestamp engine").selectOption("whisper");
    await expect(page.getByLabel("Timestamp engine")).toHaveValue("whisper");
    await page.getByRole("button", {name: "Add voice", exact: true}).click();
    await expect(page.getByLabel("Name")).toBeVisible();
    await expect(page.getByLabel("Reference ID", {exact: true})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  });

  test(`voice management paginates and fits ${viewport.width}px`, async ({page}) => {
    await page.setViewportSize(viewport);
    await mockLocalApi(page);
    await page.goto("/");
    await page.getByRole("textbox", {name: "Script", exact: true}).fill("Keep the current narration.");
    await page.getByRole("link", {name: "Voices", exact: true}).click();
    await expect(page.getByRole("heading", {name: "Voice library"})).toBeVisible();
    await expect(page.getByText("Narration style 1", {exact: true})).toBeVisible();
    await expect(page.getByRole("link", {name: "Open Original Fish voice in Fish Audio"})).toHaveAttribute("href", "https://fish.audio/app/m/b0204e37cbc94a16954c78697b844af2/");
    await expect(page.getByText("Voice 10", {exact: true})).toHaveCount(0);
    await page.getByRole("button", {name: "Next page"}).click();
    await page.getByRole("button", {name: "Use Voice 11"}).click();
    await expect(page.getByRole("textbox", {name: "Script", exact: true})).toHaveValue("Keep the current narration.");
    await expect(page.getByRole("combobox", {name: "Fish voice"})).toHaveValue("voice-11");
    await page.getByRole("link", {name: "Voices", exact: true}).click();
    await page.getByRole("button", {name: "Add voice", exact: true}).click();
    await page.getByLabel("Name", {exact: true}).fill("FairyTail");
    await page.getByLabel("Description", {exact: true}).fill("Storytelling, narrating");
    await page.getByLabel("Reference ID", {exact: true}).fill("https://fish.audio/app/m/689b47ca83dd48dba90b160affb8a118/");
    await page.getByLabel("Reference ID", {exact: true}).press("Tab");
    await expect(page.getByLabel("Reference ID", {exact: true})).toHaveValue("689b47ca83dd48dba90b160affb8a118");
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  });

  test(`audio is playable before manual transcription at ${viewport.width}px`, async ({page}) => {
    await page.setViewportSize(viewport);
    await mockLocalApi(page);
    let generated = 0;
    let finish = false;
    const audioOnly = {
      id: "manual", engine: "fish_audio", state: "complete", phase: "Audio ready", progress: 1, error: null,
      audio_url: "/api/jobs/manual/audio", download_url: "/api/jobs/manual/download", filename: "preview.mp3", duration: 2.9,
      segments: [], words: [], transcript: null, timing_source: null, transcription_state: "idle", transcription_error: null,
    };
    await page.route("**/api/jobs", (route) => {
      generated += 1;
      expect(route.request().postDataJSON().auto_transcribe).toBe(false);
      return route.fulfill({status: 202, json: audioOnly});
    });
    await page.route("**/api/jobs/manual/audio", (route) => route.fulfill({path: "public/voice-samples/af_heart.mp3", contentType: "audio/mpeg"}));
    await page.route("**/api/jobs/manual/transcript", (route) => {
      expect(route.request().postDataJSON()).toEqual({timestamp_engine: "whisperx"});
      return route.fulfill({status: 202, json: {...audioOnly, transcription_state: "queued", transcription_engine: "whisperx"}});
    });
    await page.route("**/api/jobs/manual", (route) => route.fulfill({json: {
      ...audioOnly, transcription_state: finish ? "complete" : "transcribing", transcription_engine: "whisperx",
      timing_source: finish ? "whisperx" : null,
      segments: finish ? [{text: "Hello, this is a quick preview of my voice.", start: .3, end: 2.8}] : [],
    }}));
    await page.goto("/");
    await page.getByRole("radio", {name: "Fish Audio S2.1 Pro Free — OpenRouter"}).check();
    await expect(page.getByRole("checkbox", {name: "Automatically transcribe generated audio"})).not.toBeChecked();
    await page.getByRole("textbox", {name: "Script", exact: true}).fill("Hello, this is a quick preview of my voice.");
    await page.getByRole("button", {name: "Generate speech"}).click();
    await page.getByRole("button", {name: "Play", exact: true}).click();
    await expect(page.getByRole("button", {name: "Pause", exact: true})).toBeVisible();
    await expect(page.getByRole("region", {name: "Timestamped transcript"})).toHaveCount(0);
    const audio = await page.getByRole("region", {name: "Generated audio"}).locator("audio").elementHandle();
    await page.getByRole("button", {name: "Transcribe audio", exact: true}).click();
    await expect(page.getByRole("button", {name: "Transcribing…"})).toBeDisabled();
    await expect(page.getByRole("link", {name: "Download MP3"})).toBeVisible();
    finish = true;
    await expect(page.getByRole("region", {name: "Timestamped transcript"})).toBeVisible();
    expect(await audio!.evaluate((element) => element.isConnected)).toBe(true);
    expect(generated).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  });
}

test("mobile controls follow the script-to-output task order", async ({page}) => {
  await page.setViewportSize({width: 375, height: 812});
  await mockLocalApi(page);
  await page.goto("/");
  const labels = await page.locator("h1, h2").allTextContents();
  expect(labels).toEqual(["Give the words a voice.", "TTS Engine", "Voice", "Expression", "Output", "Transcript"]);
  await page.getByRole("textbox", {name: "Script", exact: true}).fill("Kokoro is private and local.");
  await expect(page.getByRole("button", {name: "Generate speech"})).toBeEnabled();
});

test("selected voice preview plays its bundled audio", async ({page}) => {
  await mockLocalApi(page);
  await page.goto("/");

  const previewResponse = page.waitForResponse((response) =>
    response.url().endsWith("/voice-samples/af_heart.mp3") && response.ok()
  );
  await page.getByRole("button", {name: "Preview Heart voice"}).click();
  await previewResponse;

  await expect(page.getByRole("button", {name: "Stop Heart preview"})).toBeVisible();
  await expect(page.getByText("Heart preview could not be played.")).toHaveCount(0);
  const media = await page.getByLabel("Voice preview").evaluate((audio: HTMLAudioElement) => ({
    paused: audio.paused,
    source: audio.currentSrc,
  }));
  expect(media.paused).toBe(false);
  expect(media.source).toContain("/voice-samples/af_heart.mp3");
});

test("copies the selected Fish reference ID and offers its sample page", async ({page, context}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await mockLocalApi(page);
  await page.goto("/");
  await page.getByRole("radio", {name: "Fish Audio S2.1 Pro Free — OpenRouter"}).check();
  await page.getByRole("button", {name: "Copy reference ID for Original Fish voice"}).click();
  await expect(page.getByText("ID copied", {exact: true})).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe("b0204e37cbc94a16954c78697b844af2");
  const sample = page.getByRole("link", {name: "Open Original Fish voice in Fish Audio"});
  await expect(sample).toHaveAttribute("href", "https://fish.audio/app/m/b0204e37cbc94a16954c78697b844af2/");
  await expect(sample).toHaveAttribute("target", "_blank");
});
