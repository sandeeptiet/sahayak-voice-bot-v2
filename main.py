from dotenv import load_dotenv
from langchain_sarvam import ChatSarvam
from langgraph.prebuilt import create_react_agent
import os

load_dotenv()

api_key = os.getenv("SARVAM_API_KEY")

llm = ChatSarvam(
    model="sarvam-105b",
    api_key=api_key,
)

system_prompt = (
    "You are a helpful assistant. "
    "Answer the user's question. If you need more information, ask for it."
)

app = create_react_agent(
    model=llm,
    tools=[],
    prompt=system_prompt,
)

def main():
    response = app.invoke({
        "messages": [
            {"role": "user", "content": "List the voice models by Sarvam"}
        ]
    })
    
    print(response["messages"][-1].content)

if __name__ == "__main__":
    main()

