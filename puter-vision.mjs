#!/usr/bin/env node
/**
 * Puter Shell Vision — Free AI screenshot analysis via Puter.js
 *
 * Usage:
 *   node puter-vision.mjs /tmp/screenshot.png "What do you see?"
 *   node puter-vision.mjs /tmp/screenshot.png "Find first survey button coords"
 *
 * Returns: AI text response to stdout
 *
 * Auth: Set PUTER_AUTH_TOKEN env var (one-time browser login via getAuthToken())
 */

import { init } from "/tmp/node_modules/@heyputer/puter.js/src/init.cjs";
import { readFileSync } from "fs";
import { resolve } from "path";

async function main() {
  const imagePath = process.argv[2];
  const prompt = process.argv[3] || "What do you see?";

  if (!imagePath) {
    console.error("Usage: node puter-vision.mjs <image.png> <prompt>");
    process.exit(1);
  }

  const token = process.env.PUTER_AUTH_TOKEN;
  if (!token) {
    console.error("Error: PUTER_AUTH_TOKEN not set.");
    console.error("Run this ONCE to get a token:");
    console.error("  node -e \"import('/tmp/node_modules/@heyputer/puter.js/src/init.cjs').then(m=>m.getAuthToken().then(t=>console.log(t)))\"");
    console.error("Then: export PUTER_AUTH_TOKEN=<token>");
    process.exit(1);
  }

  try {
    const puter = init(token);

    // Read image
    const imageBuffer = readFileSync(resolve(imagePath));
    const filename = `survey_${Date.now()}.png`;

    // Upload to Puter cloud (free storage)
    const file = await puter.fs.write(filename, imageBuffer);
    const imageUrl = await puter.fs.getReadURL(file.path);

    // Vision analysis
    const answer = await puter.ai.chat(prompt, imageUrl, {
      model: "gpt-5.4-nano",
    });

    console.log(answer);
  } catch (err) {
    console.error("Puter error:", err.message);
    process.exit(2);
  }
}

main();
