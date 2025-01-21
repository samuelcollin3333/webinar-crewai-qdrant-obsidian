# webinar-email-assistant-crewai-obsidian

This repository contains materials from the hands-on webinar "[Building Intelligent Agentic RAG with CrewAI and 
Qdrant](https://try.qdrant.tech/agentic-rag-crewai)". It implements an agentic RAG system that uses your existing 
[Obsidian](https://obsidian.md/) Vault as a knowledge base to draft emails in Gmail Inbox.

## Software Stack

The project is built using Python and integrates with external services through their APIs. **The agentic behaviors are 
implemented using [CrewAI](https://www.crewai.com/), with [Qdrant](https://qdrant.tech/) serving as the memory layer for 
the system.**

## Prerequisites

You'll need access to a Qdrant instance, which can be set up in one of two ways:

1. Install and run it locally on your machine.
2. Sign up for a free account on [Qdrant Cloud](https://cloud.qdrant.io/).

Either option will provide you with a URL to connect to your instance. The cloud version will also provide an API key 
for authentication.

You'll need Python 3.10 or higher installed, and we recommend using Poetry for dependency management. Since we'll be 
working with SaaS models over API, no GPU access is required. Install all necessary libraries with a single command:

```shell
poetry install
```

The project uses different LLMs for different tasks, specifically [Gemini](https://ai.google.dev/) and 
[Claude](https://www.anthropic.com/api). You'll need to obtain API keys for both services. **While you can swap these 
models with alternatives in the code, we cannot guarantee the system will maintain the same performance level.** CrewAI 
makes model switching straightforward, allowing for easy experimentation.

Optionally, you can use [AgentOps](https://agentops.ai/) for observability. This requires signing up for an account and 
obtaining an API key.

### Configuration

Create a `.env` file in the root directory with the following entries:

```dotenv
# Qdrant configuration
QDRANT_LOCATION=http://localhost:6333
QDRANT_API_KEY=

# LLM providers
GEMINI_API_KEY=YOUR_API_KEY
ANTHROPIC_API_KEY=YOUR_API_KEY

# Observability with AgentOps
# Leave empty if you don't want to use AgentOps
AGENTOPS_API_KEY=

# Obsidian configuration
OBSIDIAN_VAULT_PATH=/path/to/vault
```

You can rename `.env.example` to `.env` and fill in the values, or set these as environment variables.

#### Google Cloud Credentials

Beyond environment variables, you'll need to set up Google Cloud Console credentials to access your Gmail account. 
Follow the [official documentation](https://developers.google.com/gmail/api/quickstart/python) to create a project and 
generate credentials. Download the credentials file and save it as `credentials.json` in the project's root directory.

#### Running Qdrant

To run Qdrant locally, use Docker. The following command pulls the latest Qdrant version and runs it:

```shell
bash scripts/run-qdrant.sh
```

Access the dashboard at http://localhost:6333/dashboard. Skip this step if you're using Qdrant Cloud.

## Usage

Run the application using:

```shell
poetry run python main.py
```

This launches two threads:

1. A filesystem watcher that monitors your Obsidian Vault for changes and updates the Qdrant index accordingly
2. A CrewAI agent that monitors your Gmail inbox and drafts responses based on knowledge stored in the Obsidian Vault

For a detailed explanation of the system and its components, refer to the [webinar 
recording](https://try.qdrant.tech/agentic-rag-crewai) and the source code in this repository.
