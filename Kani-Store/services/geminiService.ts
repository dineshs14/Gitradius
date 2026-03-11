import { GoogleGenAI, Type, Chat } from "@google/genai";
import type { AnalyzedItem, ChatMessage } from '../types';

const API_KEY = process.env.API_KEY;

if (!API_KEY) {
  console.warn("API_KEY not found in environment variables. Gemini features will not work.");
}

const ai = new GoogleGenAI({ apiKey: API_KEY! });
const geminiFlash = "gemini-2.5-flash";

const fileToGenerativePart = async (file: File) => {
  const base64EncodedDataPromise = new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve((reader.result as string).split(',')[1]);
    reader.readAsDataURL(file);
  });
  return {
    inlineData: { data: await base64EncodedDataPromise, mimeType: file.type },
  };
};

export const analyzeShoppingList = async (imageFile: File): Promise<AnalyzedItem[]> => {
  if (!API_KEY) {
    throw new Error("API Key is not configured.");
  }
  
  try {
    const imagePart = await fileToGenerativePart(imageFile);
    const textPart = {
      text: "Analyze this image of a shopping list (it could be handwritten or typed). Identify each grocery item and its quantity if specified. Return the result as a JSON array. Each object in the array should have 'itemName' and 'quantity' properties. For example: `[{ \"itemName\": \"Tomatoes\", \"quantity\": \"1kg\" }]`. Ignore any non-grocery items or scribbles.",
    };

    const response = await ai.models.generateContent({
      model: geminiFlash,
      contents: { parts: [imagePart, textPart] },
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              itemName: {
                type: Type.STRING,
                description: 'The name of the grocery item.',
              },
              quantity: {
                type: Type.STRING,
                description: 'The quantity or weight of the item (e.g., "1kg", "2 packets").',
              },
            },
            required: ["itemName", "quantity"],
          },
        },
      },
    });

    const jsonString = response.text.trim();
    const result = JSON.parse(jsonString);
    return result as AnalyzedItem[];

  } catch (error) {
    console.error("Error analyzing shopping list with Gemini:", error);
    throw new Error("Failed to analyze the shopping list. The AI model might be busy or the image is unreadable. Please try again.");
  }
};


class KaniChatService {
  private chat: Chat | null = null;

  constructor() {
    if (API_KEY) {
      this.initializeChat();
    }
  }

  private initializeChat() {
    this.chat = ai.chats.create({
      model: geminiFlash,
      config: {
        systemInstruction: `You are "Kani Assistant", a friendly and helpful AI for "Kani Store", an online Indian grocery store. 
        - Your goal is to assist users cheerfully and efficiently.
        - The store was founded in 2000 by Murugesan. It's also known as "Annachi Kadai".
        - You can answer questions about products, suggest simple recipes using store items, and help users find what they're looking for.
        - Keep your answers concise and easy to understand.
        - You cannot perform actions like adding items to a cart or checking order status. You can only provide information.
        - If you don't know an answer, say so politely.`,
      },
    });
  }

  async sendMessage(message: string): Promise<string> {
    if (!this.chat) {
       return "I'm sorry, the chat service is not available right now.";
    }
    try {
        const response = await this.chat.sendMessage({ message });
        return response.text;
    } catch (error) {
        console.error("Error sending chat message to Gemini:", error);
        return "I'm having a little trouble connecting. Please try again in a moment.";
    }
  }
}

export const ChatService = new KaniChatService();
