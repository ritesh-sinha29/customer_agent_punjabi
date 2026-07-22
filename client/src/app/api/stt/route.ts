import { NextResponse } from "next/server";

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

    // Step 2: Use Groq Llama 3.3 70B to convert English/Hinglish transcription into clean English sentence
    if (transcribedEnglishText) {
      try {
        const llmRes = await fetch(
          "https://api.groq.com/openai/v1/chat/completions",
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${apiKey}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              model: "llama-3.3-70b-versatile",
              messages: [
                {
                  role: "system",
                  content:
                    "You are an expert AI assistant for a dairy farming app. Convert the transcribed input text (which may be in English, Hinglish, or Romanized Punjabi) into a clean, accurate, natural English question or statement. Do NOT add any preamble, conversational filler, or quotes. Output ONLY the clean English sentence.",
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
          console.error(
            "Llama translation returned error status:",
            llmRes.status,
          );
        }
      } catch (llmErr) {
        console.error("Groq LLM translation error:", llmErr);
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
