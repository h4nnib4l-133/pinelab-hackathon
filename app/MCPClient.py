import json
import os

import openai
import requests
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ── 1. Load env vars ───────────────────────────────────────────────────────────
load_dotenv()
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

app = App(token=SLACK_BOT_TOKEN)

with open("mcp_server.json", "r") as f:
    MCP_FUNCTIONS = json.load(f)["functions"]

print(f"{MCP_FUNCTIONS}")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000")

conversations: dict[str, list[dict]] = {}

SYSTEM_PROMPT = """
You are PineGPT, a merchant-insights assistant.
Answer merchant questions about payments (revenue, refunds, success rates, anomalies)
with concise data-driven insights. Provide root-cause analysis when asked "why,"
and include recommendations where relevant.
"""


def chat_with_openai(channel: str, user_input: str) -> str:
    print("Running OpenAI...")

    if channel not in conversations:
        conversations[channel] = [{"role": "system", "content": SYSTEM_PROMPT}]

    conversations[channel].append({"role": "user", "content": user_input})

    print(f"{conversations}")
    resp = openai.chat.completions.create(
        model="gpt-4-0613",
        messages=conversations[channel],
        temperature=0.2,
        functions=MCP_FUNCTIONS,
        function_call="auto",
    )

    msg = resp.choices[0].message

    if msg.function_call:
        fn_name = msg.function_call.name
        fn_args = json.loads(msg.function_call.arguments)

        # Call MCP tool
        r = requests.post(
            f"{MCP_SERVER_URL}/functions/{fn_name}",
            json=fn_args,
        )
        r.raise_for_status()
        result = r.json()

        # Append tool result
        conversations[channel].append(
            {"role": "function", "name": fn_name, "content": json.dumps(result)}
        )

        # Follow-up completion with tool output
        followup = openai.chat.completions.create(
            model="gpt-4-0613", messages=conversations[channel]
        )
        assistant_msg = followup.choices[0].message.content
    else:
        assistant_msg = msg.content

    conversations[channel].append({"role": "assistant", "content": assistant_msg})
    return assistant_msg


@app.event("app_mention")
def handle_app_mention(event, say):
    user = event["user"]
    channel = event["channel"]
    text = event["text"].split(">", 1)[-1].strip()

    say(f"Processing your question, <@{user}>… 🤖")
    try:
        answer = chat_with_openai(channel, text)
        print(f"{answer}")
        say(f"<@{user}> {answer}")
    except Exception as e:
        say(f":warning: Oops, something went wrong: {e}")


@app.event("message")
def handle_message_events(event, say):
    if event.get("channel_type") == "im" and not event.get("bot_id"):
        user = event["user"]
        channel = event["channel"]
        text = event["text"]

        say(f"Got it, <@{user}>—thinking… 🤖")
        try:
            answer = chat_with_openai(channel, text)
            say(f"<@{user}> {answer}")
        except Exception as e:
            say(f":warning: Oops, something went wrong: {e}")


if __name__ == "__main__":
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
