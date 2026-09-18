import { defineAgent } from "eve";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";

const openrouter = createOpenAICompatible({
  name: "openrouter",
  baseURL: "https://openrouter.ai/api/v1",
  apiKey: process.env.OPENROUTER_API_KEY ?? "",
});

export default defineAgent({
  model: openrouter("qwen/qwen3.7-flash"),
  modelContextWindowTokens: 131072,
  compaction: { modelContextWindowTokens: 131072 },
});
