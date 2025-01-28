import logging
import signal
from pathlib import Path

# Configure logging first, before any other operations
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.debug("Starting script...")
logger.debug("Loading config module...")

import config  # Import config after logging is configured

# Remove filesystem observer imports since we're using API
# from watchdog.observers import Observer as FileSystemListener, Observer

#from email_assistant.gmail.handlers import AgenticAutoReplyHandler
#from email_assistant.gmail.inbox import GmailInboxListener, GmailInboxState
from email_assistant.notion.handlers import NotionToQdrantHandler

# import agentops  # Comment out or remove this line

# Set the default signal handler for SIGINT, so the KeyboardInterrupt exception is raised
signal.signal(signal.SIGINT, signal.default_int_handler)

# Optional: Initialize AgentOps if the API key is provided
# if config.agentops_api_key is not None:
#     agentops.init(api_key=config.agentops_api_key)

WORKING_DIR = Path(__file__).parent
GMAIL_INBOX_STATE_FILE = WORKING_DIR / "gmail_inbox_state.json"


def create_notion_sync():
    """
    Sync Notion content into the knowledge base.
    """
    # Add debug logging for configuration values
    logger.debug("Configuration values:")
    logger.debug("Embedder config: %s", config.embedder_config)
    logger.debug("Qdrant location: %s", config.qdrant_location)
    logger.debug("Qdrant collection: %s", config.qdrant_collection_name)
    logger.debug("Notion API key present: %s", bool(config.notion_api_key))

    logger.info("Initializing Notion sync")

    # Create handler for Notion integration
    handler = NotionToQdrantHandler(
        embedder_config=config.embedder_config,
        qdrant_location=config.qdrant_location,
        qdrant_api_key=config.qdrant_api_key,
        notion_api_key=config.notion_api_key
    )

    # Initialize the Qdrant collection with existing content
    handler.initialize()
    
    return handler


#def create_gmail_listener() -> GmailInboxListener:
    """
    Monitor the Gmail inbox for new emails and handle them accordingly.
    """
    logger.info("Monitoring mailbox for new emails...")

    # Load the previous state of the Gmail inbox
    if GMAIL_INBOX_STATE_FILE.exists():
        gmail_state = GmailInboxState.load_state(GMAIL_INBOX_STATE_FILE)
    else:
        # By default, our listener will process all the unread threads from the past.
        # Please set process_all_unread_threads=False if you want to process only new threads.
        gmail_state = GmailInboxState(process_all_unread_threads=True)

    # Create an agentic auto-reply handler
    auto_reply_handler = AgenticAutoReplyHandler(
        config.embedder_config, config.qdrant_location, config.qdrant_api_key
    )

    # Start the listener so that it can monitor the mailbox
    listener = GmailInboxListener(
        WORKING_DIR,
        state=gmail_state,
        polling_time_sec=60,  # We poll every minute
    )
    listener.add_handler(auto_reply_handler)
    return listener


if __name__ == "__main__":
    # Set logging to DEBUG level to see configuration values
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Add early configuration logging
    logger.debug("Initial Configuration values:")
    logger.debug("Embedder config: %s", config.embedder_config)
    logger.debug("Embedder provider: %s", config.embedder_config.get("provider"))
    logger.debug("Embedder API key present: %s", bool(config.embedder_config.get("config", {}).get("api_key")))
    logger.debug("Qdrant location: %s", config.qdrant_location)
    logger.debug("Qdrant collection: %s", config.qdrant_collection_name)
    logger.debug("Notion API key present: %s", bool(config.notion_api_key))

    logger.info("Starting Notion sync")
    notion_handler = create_notion_sync()

    try:
        # Keep the program running
        signal.pause()
    except KeyboardInterrupt as e:
        logger.info("Stopping Notion sync...")
        logger.info("Monitoring stopped! Exiting.")
