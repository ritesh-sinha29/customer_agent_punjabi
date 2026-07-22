import fs from "fs";
import { NextResponse } from "next/server";
import path from "path";

function getOpenaiApiKey(): string {
  try {
    const envPath = path.join(process.cwd(), ".env");
    if (fs.existsSync(envPath)) {
      const content = fs.readFileSync(envPath, "utf-8");
      const match = content.match(/^OPENAI_API_KEY\s*=\s*([^\r\n]+)/m);
      if (match && match[1]) {
        return match[1].trim().replace(/^["']|["']$/g, "");
      }
    }
  } catch (error) {
    console.error("Error reading OPENAI_API_KEY from .env file:", error);
  }
  return process.env.OPENAI_API_KEY || "";
}

export async function POST(req: Request) {
  try {
    const apiKey = process.env.GROQ_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: "GROQ_API_KEY is not configured on Next.js server." },
        { status: 500 },
      );
    }

    const formData = await req.formData();
    const audioFile = formData.get("audio") || formData.get("file");

    if (!audioFile || !(audioFile instanceof Blob)) {
      return NextResponse.json(
        { error: "No audio file found in request." },
        { status: 400 },
      );
    }

    const groqFormData = new FormData();
    groqFormData.append("file", audioFile, "audio.webm");
    groqFormData.append("model", "whisper-large-v3-turbo");
    groqFormData.append("language", "en");

    // Domain prompt to guide English transcription
    groqFormData.append(
      "prompt",
      "The audio contains spoken Punjabi, Hindi or Hinglish about cows, buffaloes, milk yield, animal feed, mineral mixture, powder, veterinary medicines, VRSA products, and livestock.",
    );

    // Step 1: Call Groq Transcriptions Endpoint with language="en"
    const response = await fetch(
      "https://api.groq.com/openai/v1/audio/transcriptions",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
        body: groqFormData,
      },
    );

    if (!response.ok) {
      const errText = await response.text();
      console.error("Groq Transcriptions API error response:", errText);
      return NextResponse.json(
        { error: `Groq STT Error: ${errText}` },
        { status: response.status },
      );
    }

    const data = await response.json();
    const transcribedEnglishText = (data.text || "").trim();

    console.log("\n========================================================");
    console.log(
      "🎤 Step 1 - GROQ ENGLISH TRANSCRIPTION:",
      transcribedEnglishText,
    );

    let finalEnglishText = transcribedEnglishText;

    // Step 2: Use OpenAI (gpt-4o-mini) to convert Romanized Punjabi / Hinglish transcription into clean English sentence
    if (transcribedEnglishText) {
      try {
        const openaiApiKey = getOpenaiApiKey();
        if (!openaiApiKey) {
          console.error("OPENAI_API_KEY is not configured on Next.js server.");
        } else {
          const llmRes = await fetch(
            "https://api.openai.com/v1/chat/completions",
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${openaiApiKey}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                model: "gpt-4o-mini",
                messages: [
                  {
                    role: "system",
                    content:
                      'You are an expert AI translator for a dairy farming and livestock app. Convert Romanized Punjabi, Hinglish, or Punjabi-style English sentences into clean, grammatically correct, natural English.\n\nEnsure Punjabi words are translated accurately:\n- "majh" or "majha" -> "buffalo" or "cow" (prefer "buffalo" as it is the literal translation, but ensure it flows naturally as livestock)\n- "kol" or "kool" -> "have" (e.g., "mere kol" or "mere kool" means "I have")\n- "panch" or "panj" -> "5" or "five"\n- "das" or "dass" -> "10" or "ten"\n- "murgian" or "murgiane" -> "hens" or "chickens"\n\nExample conversions:\n- "Mere kool panch majh ne das murgiane." -> "I have 5 buffaloes and 10 hens."\n- "mere kol do majha te ik gaa hai" -> "I have two buffaloes and one cow."\n\nTranslate the user\'s input directly into natural English. Do NOT add any preamble, explanation, conversational filler, or quotes. Output ONLY the clean English sentence.',
                  },
                  {
                    role: "user",
                    content: transcribedEnglishText,
                  },
                ],
                temperature: 0.1,
                max_tokens: 150,
              }),
            },
          );

          if (llmRes.ok) {
            const llmData = await llmRes.json();
            const translated = llmData.choices?.[0]?.message?.content?.trim();
            if (translated) {
              finalEnglishText = translated.replace(/^["']|["']$/g, "");
            }
          } else {
            const errText = await llmRes.text();
            console.error(
              "OpenAI translation returned error status:",
              llmRes.status,
              errText,
            );
          }
        }
      } catch (llmErr) {
        console.error("OpenAI LLM translation error:", llmErr);
      }
    }

    console.log("🇬🇧 Step 2 - FINAL ENGLISH OUTPUT:", finalEnglishText);
    console.log("========================================================\n");

    return NextResponse.json({
      success: true,
      rawTranscription: transcribedEnglishText,
      text: finalEnglishText,
    });
  } catch (error: any) {
    console.error("Error in Next.js /api/stt route:", error);
    return NextResponse.json(
      { error: error?.message || "Failed to process audio transcription." },
      { status: 500 },
    );
  }
}
