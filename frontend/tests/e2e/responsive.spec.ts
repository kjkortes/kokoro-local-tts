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
  defaults: {language: "a", voice: "af_heart", preset: "neutral", format: "wav"},
  limits: {speed: {min: .5, max: 2}, pitch: {min: -4, max: 4}, tempo: {min: .75, max: 1.25}, pause_scale: {min: .5, max: 2}, volume: {min: 0, max: 1.5}},
};

async function mockLocalApi(page: import("@playwright/test").Page) {
  await page.route("**/api/config", (route) => route.fulfill({json: config}));
  await page.route("**/api/status", (route) => route.fulfill({json: {state: "ready", device: "cpu", version: "0.1.0", detail: null}}));
}

for (const viewport of [{width: 375, height: 812}, {width: 1440, height: 900}]) {
  test(`workspace fits ${viewport.width}px without horizontal overflow`, async ({page}) => {
    await page.setViewportSize(viewport);
    await mockLocalApi(page);
    await page.goto("/");
    await expect(page.getByRole("heading", {name: "Give the words a voice."})).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    expect(overflow).toBe(false);
    await expect(page.getByLabel("Script")).toBeVisible();
    await expect(page.getByRole("button", {name: "Generate speech"})).toBeDisabled();
  });
}

test("mobile controls follow the script-to-output task order", async ({page}) => {
  await page.setViewportSize({width: 375, height: 812});
  await mockLocalApi(page);
  await page.goto("/");
  const labels = await page.locator("h1, h2").allTextContents();
  expect(labels).toEqual(["Give the words a voice.", "Voice", "Expression", "Output"]);
  await page.getByLabel("Script").fill("Kokoro is private and local.");
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
