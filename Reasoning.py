import ollama,json
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

