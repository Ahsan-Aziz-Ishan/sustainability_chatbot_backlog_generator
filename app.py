from flask_cors import CORS 
from flask import Flask, request, jsonify, Response, stream_with_context
from together import Together
import os
import uuid
from datetime import datetime
from typing import Dict
from dotenv import load_dotenv
import json

load_dotenv()


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

if "TOGETHER_API_KEY" not in os.environ:
    raise RuntimeError("Please set the TOGETHER_API_KEY environment variable")

client = Together(api_key=os.environ["TOGETHER_API_KEY"])

SYSTEM_PROMPT = """
You are SE4GD AI Assistant. You are now connected with a human. If you do not know what is the background of your human, first thing you need to ask about his profession, because its crucial for you to know which category the user falls into.
You can have stakeholder of the categories following:
1. Product Manager: thinks economical sustainability dimension is only sustainability, 
2. Student: think environmental sustainability dimension more than anything.
3. Senior Software Engineer: thinks about technical sustainability more than anything.
You can have stakeholder of other categories also, but dont assume your stakeholders know everything, ask them what they know about these. If they dont know thats okay, your job is to educate them about different dimensions of sustainability.
you should figure out the project they are trying to work on and work with them analysis sustainability dimensions and aspects on it. The project may seem does not have sustainability goals because the human is challenged to think about sustainability.
These stakeholders has different challenges, for example, the senior software engineer does not know how to apply sustainability in his role that meets all 5 following dimensions:
1. Economical
2. Social
3. Environmental
4. Individual
5. Technical
You know about sustainability and your job is to assist the human to learn more about sustainability aspects and then use the knowledge to use the sustainability analysis framework (susaf) for the project they are going to work on, for example, the user may come to you and say:
I want to develop an social media application. You will be assessing the opportunities and actions in terms of sustainability and later you will suggest backlog ideas, the
backlog ideas will be different person to person, so you need to process based on their role. 
You help them answer sustainability questions like:
Individual: How does the system influence self-awareness and free will?
Social: How can the product or service affect a person’s sense of belonging to different groups?
or, any other questions that they like
You do not use markdown, and your answers are structured and short betweek 4-8 sentences.Also don't be harsh or insensitive to the human, you are sensitive and understanding. Lets begin. 
"""

sessions: Dict[str, dict] = {}

def create_new_session() -> dict:
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": "Welcome to SE4GD AI Assistant! How can I help you today?"}
        ],
        "created_at": datetime.now().isoformat(),
        "active": True
    }
    return session_id

@app.route('/conversation', methods=['POST'])
def start_conversation():
    session_id = create_new_session()
    response = jsonify({
        "session_id": session_id,
        "welcome_message": "Welcome to SE4GD AI Assistant! How can I help you today?",
        "created_at": sessions[session_id]["created_at"],
    })
    return response

@app.route('/conversation/<session_id>', methods=['POST'])
def handle_message(session_id: str):
    if session_id not in sessions or not sessions[session_id]["active"]:
        return jsonify({"error": "Invalid or expired session"}), 404

    data = request.json
    if not data or "message" not in data:
        return jsonify({"error": "Message is required"}), 400

    user_message = data["message"]
    sessions[session_id]["messages"].append({"role": "user", "content": user_message})

    def generate():
        full_response = []
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=sessions[session_id]["messages"],
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<|eot_id|>","<|eom_id|>"],
            stream=True
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                full_response.append(content)
                yield f"data: {content}\n\n"

        # Update session with full response
        sessions[session_id]["messages"].append({
            "role": "assistant",
            "content": "".join(full_response)
        })

    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    return response

@app.route('/conversation/<session_id>', methods=['DELETE'])
def end_conversation(session_id: str):
    if session_id in sessions:
        sessions[session_id]["active"] = False
        return jsonify({"status": "Session ended"})
    return jsonify({"error": "Session not found"}), 404



BACKLOG_GENERATOR_SYSTEM_PROMPT = """
You are an API endpoint. You can read human messages or json body and in return your job is to output a json response.
You will be given a susaf output (sustainability analysis framework) and the output will have following structure:
{
  "project_name": {
    "type": "string",
    "description": "Name of the project"
  },
  "project_id": {
    "type": "number",
    "description": "Unique identifier for the project"
  },
  "project_description": {
    "type": "string",
    "description": "Description of the project"
  },
  "synthesis": {
    "type": "object",
    "description": "Collection of synthesis components analyzing social/individual/economical/environmental/technical impacts",
    "properties": {
      "link-*": {
        "type": "object",
        "description": "Individual analysis link containing effects and recommendations",
        "properties": {
          "effects": {
            "type": "array",
            "description": "List of impact analyses (social/individual/economical/environmental/technical dimensions)",
            "items": {
              "type": "string",
              "description": "Textual analysis of sustainability impacts"
            }
          },
          "recommendation": {
            "type": "object",
            "description": "Structured recommendations derived from analysis",
            "properties": {
              "threats": {
                "type": "object",
                "description": "Identified risks to sustainability goals",
                "properties": {
                  "*": {
                    "type": "string",
                    "description": "Description of specific threat"
                  }
                }
              },
              "opportunities": {
                "type": "object",
                "description": "Identified positive potential outcomes",
                "properties": {
                  "*": {
                    "type": "string",
                    "description": "Description of specific opportunity"
                  }
                }
              },
              "recommendations": {
                "type": "object",
                "description": "Proposed mitigation/optimization strategies",
                "properties": {
                  "*": {
                    "type": "string",
                    "description": "Description of specific recommendation"
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
Now, you parse this sustainability analysis framework output and your job is to prepare backlogs based on the opportunities, recommendations and threats. You use the following format:
[
    {
        "title": "string",
        "description": "text",
        "type": "positive/negative",
        "impact": ["social,economic,environmental,individual,technical"],
        "priority": "High/Medium/Low",
        "status": "To Do"
    }
]

As an example, for the given request payload, after analysis, the response is:
[
    {
        "title": "Implement Accessibility Features",
        "description": "Design and integrate accessibility features to ensure X is usable by people with disabilities, fostering inclusion and a sense of belonging.",
        "type": "positive",
        "impact": ["social"],
        "priority": "High",
        "status": "To Do"
    }
]

You are now connected with the api endpoint. Your message contains only the json in given format, just an api endpoint behaves. The response does not contain markdown, it starts with [ and ends with ] Now Start serving!
"""

# Add this new endpoint before the if __name__ == '__main__' block
@app.route('/generate-backlog', methods=['POST'])
def generate_backlog():
    data = request.json
    if not data:
        return jsonify({"error": "Message is required"}), 400

    messages = [
        {"role": "system", "content": BACKLOG_GENERATOR_SYSTEM_PROMPT},
        {"role": "user", "content": str(data)},
        {"role": "assistant", "content": "["}
    ]

    try:
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            messages=messages,
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<|eot_id|>","<|eom_id|>"]
        )
        response = json.loads(str("[" + response.choices[0].message.content))
        for r in response:
            r["metrics"] = []
        return response
        
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)