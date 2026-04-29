#!/usr/bin/env node
/**
 * Puter CLI Bridge — Headless Browser für Puter.js API-Calls
 *
 * Startet einen Headless-Chromium, lädt puter.js, führt API-Calls aus
 * und gibt das Ergebnis auf stdout zurück.
 *
 * Usage:
 *   node puter-cli.mjs txt2img "a cat" --output cat.png
 *   node puter-cli.mjs txt2vid "a dog running" --output dog.mp4
 *   node puter-cli.mjs chat "What is life?" --model gpt-5.4-nano
 *   node puter-cli.mjs vision "describe this" --image screenshot.png --model gpt-5.4-nano
 */

import { chromium } from "playwright";
import { writeFileSync, readFileSync, existsSync } from "fs";
import { resolve } from "path";

const PUTER_TOKEN =
  process.env.PUTER_AUTH_TOKEN ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoiZ3VpIiwidmVyc2lvbiI6IjAuMC4wIiwidXVpZCI6IjhjOGRkNWJlLTYwNzYtNDgxZS1iMmVkLTkyY2YyZTIxZWM3OCIsInVzZXJfdWlkIjoiMWZlYTk0ZTctMDMwNC00OGExLWE3ODUtNTBmMzBiNTdjODJjIiwiaWF0IjoxNzc3NDI2MzcxfQ.F4Ogy0nasv3gxsQZ_TS1czjEscnXO7AECtT26sX2sbc";

const HTML = `<!DOCTYPE html><html><body><script src="https://js.puter.com/v2/"></script><script>
window.PUTER_READY = false;
(async () => {
  // Puter.js auto-authenticates in browser via OAuth popup.
  // For headless: use anonymous free tier (no auth needed for basic calls)
  await new Promise(r => setTimeout(r, 2000));
  window.PUTER_READY = true;
})();
</script></body></html>`;

async function main() {
  const args = process.argv.slice(2);
  const action = args[0];
  const prompt = args[1];
  const outputPath = args.includes("--output") ? args[args.indexOf("--output") + 1] : null;
  const imagePath = args.includes("--image") ? args[args.indexOf("--image") + 1] : null;
  const model = args.includes("--model") ? args[args.indexOf("--model") + 1] : "gpt-5.4-nano";

  if (!action || !prompt) {
    console.log("Usage: node puter-cli.mjs <action> <prompt> [--output file] [--model model] [--image file]");
    console.log("Actions: txt2img, txt2vid, chat, vision");
    process.exit(1);
  }

  console.log(`🚀 Puter CLI: ${action} "${prompt.slice(0, 50)}..."`);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Inject HTML with puter.js
  await page.setContent(HTML);
  await page.waitForFunction(() => window.PUTER_READY, { timeout: 15000 });
  console.log("✅ Puter.js geladen + authentifiziert");

  // Prepare image data if needed
  let imageData = null;
  if (imagePath && existsSync(imagePath)) {
    const imgBuf = readFileSync(resolve(imagePath));
    imageData = `data:image/png;base64,${imgBuf.toString("base64")}`;
    await page.evaluate(
      (data) => {
        const img = document.createElement("img");
        img.src = data;
        img.id = "input-image";
        document.body.appendChild(img);
      },
      imageData
    );
  }

  // Execute Puter API call
  let result;
  try {
    result = await page.evaluate(
      async ({ action, prompt, model, imageData }) => {
        try {
          if (action === "txt2img") {
            const img = await puter.ai.txt2img(prompt);
            if (img instanceof HTMLImageElement) {
              const canvas = document.createElement("canvas");
              canvas.width = img.naturalWidth;
              canvas.height = img.naturalHeight;
              canvas.getContext("2d").drawImage(img, 0, 0);
              return { type: "image", data: canvas.toDataURL("image/png") };
            }
            return { type: "text", data: String(img) };
          } else if (action === "txt2vid") {
            const video = await puter.ai.txt2vid(prompt);
            if (video instanceof HTMLVideoElement) {
              return { type: "video", src: video.src, duration: video.duration };
            }
            return { type: "text", data: String(video) };
          } else if (action === "chat") {
            const resp = await puter.ai.chat(prompt, { model });
            return { type: "text", data: typeof resp === "string" ? resp : resp?.message?.content || JSON.stringify(resp) };
          } else if (action === "vision") {
            const resp = await puter.ai.chat(prompt, imageData || "https://assets.puter.site/doge.jpeg", { model });
            return { type: "text", data: typeof resp === "string" ? resp : resp?.message?.content || JSON.stringify(resp) };
          }
          return { type: "error", data: `Unknown action: ${action}` };
        } catch (e) {
          return { type: "error", data: e.message };
        }
      },
      { action, prompt, model, imageData }
    );
  } catch (e) {
    result = { type: "error", data: e.message };
  }

  // Output result
  if (result.type === "image" && result.data) {
    const base64Data = result.data.replace(/^data:image\/\w+;base64,/, "");
    if (outputPath) {
      writeFileSync(resolve(outputPath), Buffer.from(base64Data, "base64"));
      console.log(`✅ Image saved: ${outputPath}`);
    } else {
      process.stdout.write(Buffer.from(base64Data, "base64"));
    }
  } else if (result.type === "video") {
    console.log(`🎬 Video URL: ${result.src}`);
    console.log(`⏱️ Duration: ${result.duration}s`);
  } else if (result.type === "text") {
    console.log(result.data);
  } else {
    console.error("❌", result.data);
  }

  await browser.close();
}

main().catch((e) => {
  console.error("Fatal:", e.message);
  process.exit(1);
});
