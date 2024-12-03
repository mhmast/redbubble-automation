// const puppeteer = require("puppeteer");
// const cheerio = require("cheerio");
// const fs = require("fs");
require("dotenv").config();


const fetch = require('node-fetch'); // Import fetch for Node.js environments

const sendPromptToChatGPT = async (prompt) => {
  const apiUrl = "https://api.openai.com/v1/chat/completions"; // OpenAI API endpoint
  const apiKey = process.env.OPENAI_API_KEY; // Replace with your OpenAI API key

  const requestBody = {
    model: "whisper-1",
    messages: [
      {
        role: "user",
        content: prompt
      }
    ],
    temperature: 0.7,
    max_tokens: 500
  };

  try {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`
      },
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      throw new Error(`API request failed with status: ${response.status} ${await response.text()}`);
    }

    const data = await response.json();
    console.log("Response from ChatGPT:", data.choices[0].message.content);
    return data.choices[0].message.content;
  } catch (error) {
    console.error("Error sending prompt to ChatGPT:", error);
  }
};

/**
 * Returns a list of today trending keywords based on input search from redbubble website. Store them in ./historic folder
 *
 * @param {string} formattedDate string date for json file name
 * @return {Array}
 */
async function getTrendingKeywordsModule() {
  try {
    
   const prompt = "give me a list of todays trending topics to print on tshirts and for each topic give me an ai prompt describing the image and return them in a json format using this schema { \"$schema\": \"http://json-schema.org/draft-04/schema#\", \"type\": \"array\", \"items\": [ { \"type\": \"object\", \"properties\": { \"date\": { \"type\": \"string\" }, \"prompt\": { \"type\": \"string\" } }, \"required\": [ \"prompt\" ] } ] }. return only this json and nothing else.";
    /*
give me a list of todays trending topics to print on tshirts and for each topic give me an ai prompt describing the image and return them in a json format using this schema { "$schema": "http://json-schema.org/draft-04/schema#", "type": "array", "items": [ { "type": "object", "properties": { "date": { "type": "string" }, "prompt": { "type": "string" } }, "required": [ "date", "prompt" ] } ] }. return only this json and nothing else.
    */
    const result = await sendPromptToChatGPT(prompt)

    
    return JSON.parse(result);
  } catch (error) {
    console.error("Error:", error);
  }
}

module.exports = {
  getTrendingKeywordsModule,
};
