import logging
import signal
from pathlib import Path
import time
import sys
from flask import Flask, render_template, request, jsonify
import threading

# Configure logging first, before any other operations
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.debug("Starting script...")
logger.debug("Loading config module...")

import config
from email_assistant.notion.handlers import NotionToQdrantHandler
from email_assistant.notion.query import NotionQuerier

# Remove filesystem observer imports since we're using API
# from watchdog.observers import Observer as FileSystemListener, Observer

#from email_assistant.gmail.handlers import AgenticAutoReplyHandler
#from email_assistant.gmail.inbox import GmailInboxListener, GmailInboxState

# import agentops  # Comment out or remove this line

# Set the default signal handler for SIGINT, so the KeyboardInterrupt exception is raised
signal.signal(signal.SIGINT, signal.default_int_handler)

# Optional: Initialize AgentOps if the API key is provided
# if config.agentops_api_key is not None:
#     agentops.init(api_key=config.agentops_api_key)

WORKING_DIR = Path(__file__).parent
GMAIL_INBOX_STATE_FILE = WORKING_DIR / "gmail_inbox_state.json"

# Reduce noise from AI processing logs
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('litellm').setLevel(logging.ERROR)
logging.getLogger('litellm.cost_calculator').setLevel(logging.ERROR)

app = Flask(__name__)
querier = None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal. Stopping services...")
    sys.exit(0)

def create_notion_sync():
    """
    Sync Notion content into the knowledge base.
    """
    SYNC_INTERVAL = 600  # 10 minutes in seconds
    
    logger.debug("Configuration values:")
    logger.debug(f"Embedder config: {config.embedder_config}")
    logger.debug(f"Qdrant location: {config.qdrant_location}")
    logger.debug(f"Qdrant collection: {config.qdrant_collection_name}")
    logger.debug(f"Notion API key present: {bool(config.notion_api_key)}")
    logger.debug(f"Sync interval: {SYNC_INTERVAL} seconds (10 minutes)")
    
    logger.info("Initializing Notion sync")
    
    handler = NotionToQdrantHandler(
        notion_api_key=config.notion_api_key,
        qdrant_location=config.qdrant_location,
        qdrant_api_key=config.qdrant_api_key,
        embedder_config=config.embedder_config
    )
    
    try:
        sync_count = 0
        while True:  # Continuous sync loop
            try:
                sync_count += 1
                start_time = time.time()
                logger.info(f"Starting Notion sync cycle #{sync_count}")
                
                handler.sync_notion_to_qdrant()
                
                end_time = time.time()
                duration = end_time - start_time
                logger.info(f"Sync cycle #{sync_count} completed in {duration:.1f} seconds")
                logger.info(f"Next sync will run in {SYNC_INTERVAL/60:.1f} minutes (at {time.strftime('%H:%M:%S', time.localtime(end_time + SYNC_INTERVAL))})")
                
                time.sleep(SYNC_INTERVAL)
                
            except KeyboardInterrupt:
                raise  # Re-raise to be handled by outer try block
            except Exception as e:
                logger.error(f"Error during sync cycle #{sync_count}: {e}")
                logger.info(f"Waiting {SYNC_INTERVAL/60:.1f} minutes before retry...")
                time.sleep(SYNC_INTERVAL)
    finally:
        logger.info("Notion sync process terminated. Goodbye!")
    
    return handler

def create_notion_querier():
    global querier
    querier = NotionQuerier(
        embedder_config=config.embedder_config,
        qdrant_location=config.qdrant_location,
        qdrant_api_key=config.qdrant_api_key
    )
    return querier

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/ask', methods=['POST'])
def ask():
    try:
        question = request.json.get('question')
        if not question:
            return jsonify({'error': 'No question provided'}), 400
        
        answer = querier.ask_question(question)
        return jsonify({'answer': answer})
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        return jsonify({'error': str(e)}), 500

def main():
    """
    Main function to handle Notion querying
    """
    try:
        # First, sync Notion data to Qdrant in a separate thread
        logger.info("Starting initial Notion sync...")
        sync_thread = threading.Thread(target=create_notion_sync, daemon=True)
        sync_thread.start()
        
        # Create querier for asking questions
        create_notion_querier()
        
        # Start the Flask application
        logger.info("Starting web interface...")
        app.run(host='0.0.0.0', port=5001, debug=False)  # Changed port to 5001

    except Exception as e:
        logger.error(f"Error in main: {e}")
        print("\nError initializing the system. Please check your configuration and try again.")

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
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
