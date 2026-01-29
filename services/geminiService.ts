import { GoogleGenAI } from "@google/genai";

let genAI: GoogleGenAI | null = null;

export const initializeGemini = () => {
  if (process.env.API_KEY) {
    genAI = new GoogleGenAI({ apiKey: process.env.API_KEY });
  }
};

const SYSTEM_INSTRUCTION = `
You are an Intelligent Building Agent, an expert in urban microclimate analysis, CFD (Computational Fluid Dynamics), and solar simulations.
You operate within a simulation workspace.
Your goal is to assist the user in setting up simulations, analyzing geometry, and interpreting results.
The current context is "Intent Analysis" and "Solver Orchestration".

If the user asks about the simulation plan, explain that you have parsed their query and are ready to configure the mesh grid.
If the user confirms a selection (like "Standard" or "High Resolution"), acknowledge it and pretend to start the simulation process.

Keep responses concise, professional, and scientific. Use the persona of a high-end technical assistant.
`;

export const sendMessageToGemini = async (message: string, history: {role: string, parts: {text: string}[]}[] = []) => {
  if (!genAI) {
    // Fallback if no API key
    return "I am running in demo mode. Please provide an API Key to enable real-time agent logic. For now, I've noted your request.";
  }

  try {
    const model = genAI.getGenerativeModel({ 
        model: "gemini-2.5-flash-latest",
        systemInstruction: SYSTEM_INSTRUCTION
    });
    
    // Convert history format if needed, but for single-turn or simple chat, simple generation is often enough.
    // Here we just use generateContent for simplicity as we manage state in React.
    const chat = model.startChat({
        history: history.map(h => ({
            role: h.role,
            parts: h.parts
        }))
    });

    const result = await chat.sendMessage(message);
    const response = result.response;
    return response.text();
  } catch (error) {
    console.error("Gemini API Error:", error);
    return "I encountered an error processing your request. Please check the system logs.";
  }
};