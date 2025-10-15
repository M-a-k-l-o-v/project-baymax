import ollama, json
from API_and_tools import *
MODEL = "llama"

def lam_reasoning(prompt):
    response = ollama.chat(
        model = MODEL,
        messages=[
            {"role": "user","content": prompt}
        ]
    )
    print(response['message']['content'])

def decide_tools(user_prompt):
    """Ask the LLM which tool to use based on the user's request."""
    
    system_prompt = """
    You are a smart assistant that selects tools to answer user questions.
    Available tools:
    - get_weather: gets the current weather for the user's location
    - get_time: gets the current local time
    - get_date: gets today's date
    - get_location: gets the user's approximate location (city, country)
    
    Respond ONLY in JSON, like one of the following:
    {"tool": "get_weather", "args": {}}
    {"tool": "get_time", "args": {}}
    {"tool": "get_date", "args": {}}
    {"tool": null, "args": {}}
    """

    response = ollama.chat(model="llama3", messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ])

    tool_decision = response["message"]["content"]

    try:
        decision = json.loads(tool_decision)
    except json.JSONDecodeError:
        decision = {"tool": None, "args": {}}
    return decision