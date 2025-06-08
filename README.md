# pinelab-hackathon

Sure! Here's your README.md file content in Markdown format:

# 📊 PineGPT – CSV-Powered Insights and Alert System

**PineGPT** is an AI-powered assistant that answers merchant queries using CSV data, with tool calling via an MCP (Model Context Protocol) server. It also supports alert scheduling using cron and can be integrated into Slack for a conversational experience.

---

## 📁 Project Structure

.
├── Dockerfile # Docker setup for running the app
├── LICENSE # Project license
├── README.md # This documentation
├── app/
│   ├── MCPClient.py # Slack-integrated client that sends queries to the MCP server
│   ├── MCPTools.py # FastAPI MCP server exposing tool functions like run_analysis, create_alert
│   ├── alerts.db # SQLite DB for storing alert jobs
│   ├── data/
│   │   └── csv/
│   │   └── settlement_data.csv # The core CSV used for insights
│   └── mcp_server.json # JSON spec for available MCP tools
├── poetry.lock # Poetry dependency lock file
└── pyproject.toml # Poetry project config


---

## 🚀 Features

- 🔍 **Run Analysis:** AI executes Python code on the CSV to extract insights.
- ⏰ **Create Alerts:** Schedule recurring analysis with conditional triggers.
- 📩 **Slack Integration:** Ask questions in natural language via Slack.
- 🐳 **Docker-Ready:** Containerized for easy deployment.
- 🧠 **LLM Tool Calling:** Connects OpenAI GPT with FastAPI-based MCP tools.

---

## ⚙️ Setup Instructions

### 1. Clone the repo

```bash
git clone https://github.com/your-org/pinegpt-csv-insights.git
cd pinegpt-csv-insights

2. Set up environment variables

Create a .env file in the root directory:

SLACK_BOT_TOKEN=your-slack-bot-token
SLACK_APP_TOKEN=your-slack-app-level-token
OPENAI_API_KEY=your-openai-api-key
MCP_SERVER_URL=http://localhost:8000

🧪 Local Development
Option A: Run without Docker

Install dependencies:

poetry install

Start the MCP Server:

cd app
python MCPTools.py

In another terminal, run the Slack client:

python MCPClient.py

Option B: Run with Docker

docker build -t pinegpt-csv .
docker run -p 8000:8000 pinegpt-csv

💬 Slack Usage

Mention the bot or DM it directly in Slack:

@PineGPT How many UPI transactions have occurred?

Bot will:

    Interpret your query

    Call the MCP server’s run_analysis tool

    Return insights directly in Slack

🛠 MCP Tools Available

Defined in app/mcp_server.json:

    run_analysis: Run custom Python over settlement_data.csv

    create_alert: Schedule periodic checks

    close_alert: Cancel a scheduled alert

🧠 Prompt Strategy

The LLM is instructed to:

    Always use settlement_data.csv

    Infer terms like "UPI" and "IRCTC" as values, not headers

    Match values fuzzily and case-insensitively

📅 Alerts via Cron

Alerts can be scheduled using standard 5-part cron syntax:

* * * * *   # every 1 minute

