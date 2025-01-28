import logging
from notion_client import Client
from email_assistant.storage import QdrantStorage
from email_assistant.crew import KnowledgeOrganizingCrew
from email_assistant.models import ContextualizedChunks
import config
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)

class NotionToQdrantHandler:
    def __init__(self, embedder_config, qdrant_location, qdrant_api_key=None, notion_api_key=None):
        """
        Initialize the NotionToQdrantHandler
        Args:
            embedder_config: Configuration for the embedder
            qdrant_location: URL of the Qdrant instance
            qdrant_api_key: API key for Qdrant (optional)
            notion_api_key: API key for Notion
        """
        self.notion = Client(auth=notion_api_key)
        self.qdrant_storage = QdrantStorage(
            type="notion-notes",  # Add the collection name
            qdrant_location=qdrant_location, 
            qdrant_api_key=qdrant_api_key,
            embedder_config=embedder_config
        )
        self.teamspace_name = "ElipsTest"
        self.crew = KnowledgeOrganizingCrew(embedder_config, qdrant_location, qdrant_api_key).crew()
        self.database_id = config.notion_database_id
        self.qdrant_client = QdrantClient(url=qdrant_location, api_key=qdrant_api_key)

    def sync_notion_to_qdrant(self):
        """Sync all content from Notion workspace to Qdrant"""
        try:
            # First, get all pages from the workspace
            pages = self.fetch_all_pages()
            logger.info(f"Found {len(pages)} pages in Notion workspace")

            # Keep track of processed pages
            processed_count = 0
            updated_count = 0
            
            # Process each page
            for page in pages:
                try:
                    page_id = page["id"]
                    last_edited_time = page["last_edited_time"]

                    # Check if page needs updating by comparing last_edited_time
                    if not self.page_needs_update(page_id, last_edited_time):
                        processed_count += 1
                        continue

                    # Process and store the page content
                    content = self.extract_content_from_page(page)
                    if content:
                        self.process_and_store_content(page_id, content, last_edited_time)
                        updated_count += 1
                    processed_count += 1

                except Exception as e:
                    logger.error(f"Error processing page {page.get('id', 'unknown')}: {e}")

            # Remove any pages that have been deleted from Notion
            self.remove_deleted_pages_from_qdrant(pages)
            
            logger.info(f"Sync completed: {processed_count} pages processed, {updated_count} pages updated")

        except Exception as e:
            logger.error(f"Error syncing Notion content: {e}")

    def fetch_all_pages(self):
        """Fetch all pages from the workspace"""
        try:
            all_pages = []
            has_more = True
            start_cursor = None
            
            while has_more:
                logger.debug("Making search request to Notion API...")
                try:
                    response = self.notion.search(
                        query="",  # Empty query to get everything
                        start_cursor=start_cursor,
                        page_size=100,
                    )
                    
                    # Log the full response structure (without content)
                    response_structure = {
                        "has_more": response.get("has_more"),
                        "next_cursor": response.get("next_cursor"),
                        "type": response.get("type"),
                        "results_count": len(response.get("results", [])),
                        "response_keys": list(response.keys())
                    }
                    logger.debug(f"Response structure: {response_structure}")
                    
                    results = response.get("results", [])
                    if results:
                        # Log details about the first result
                        first_result = results[0]
                        logger.debug(f"First result keys: {list(first_result.keys())}")
                        logger.debug(f"First result type: {first_result.get('object')}")
                        logger.debug(f"First result URL: {first_result.get('url', 'no url')}")
                    
                    logger.debug(f"Found {len(results)} results in this batch")
                    all_pages.extend(results)
                    
                    has_more = response.get("has_more", False)
                    start_cursor = response.get("next_cursor") if has_more else None
                    logger.debug(f"Has more: {has_more}, Next cursor: {start_cursor}")

                except Exception as e:
                    logger.error(f"Error during search request: {e}")
                    logger.exception(e)
                    break

            logger.debug(f"Total results found: {len(all_pages)}")
            # Log the types of objects we found
            object_types = set(page.get('object') for page in all_pages)
            logger.debug(f"Found object types: {object_types}")
            
            return all_pages

        except Exception as e:
            logger.error(f"Error fetching pages from Notion: {e}")
            logger.exception(e)  # This will print the full stack trace
            return []

    def extract_content_from_page(self, page):
        """Extract content from a Notion page"""
        try:
            # Get the page content
            page_id = page["id"]
            blocks = self.notion.blocks.children.list(block_id=page_id)
            
            # Process blocks into text
            content = []
            for block in blocks["results"]:
                if block["type"] == "paragraph":
                    text = block.get("paragraph", {}).get("rich_text", [])
                    content.extend([t.get("plain_text", "") for t in text])
                elif block["type"] == "heading_1":
                    text = block.get("heading_1", {}).get("rich_text", [])
                    content.extend([f"# {t.get('plain_text', '')}" for t in text])
                elif block["type"] == "heading_2":
                    text = block.get("heading_2", {}).get("rich_text", [])
                    content.extend([f"## {t.get('plain_text', '')}" for t in text])
                elif block["type"] == "heading_3":
                    text = block.get("heading_3", {}).get("rich_text", [])
                    content.extend([f"### {t.get('plain_text', '')}" for t in text])
                # Add more block types as needed

            return "\n".join(content)

        except Exception as e:
            logger.error(f"Error extracting content from page {page.get('id', 'unknown')}: {e}")
            return ""

    def page_needs_update(self, page_id, last_edited_time):
        """Check if a page needs to be updated in Qdrant"""
        try:
            # Get the last edited time from Qdrant metadata
            points = self.qdrant_client.scroll(
                collection_name="notion-notes",
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="notion_page_id",
                            match=MatchValue(value=page_id)
                        )
                    ]
                ),
                limit=1
            )
            
            if not points[0]:
                return True  # Page doesn't exist in Qdrant
            
            stored_last_edited = points[0][0].payload.get("last_edited_time")
            
            if not stored_last_edited:
                return True  # No last_edited_time stored
            
            return stored_last_edited != last_edited_time
            
        except Exception as e:
            logger.error(f"Error checking page update status: {e}")
            return True  # Update on error to be safe

    def process_and_store_content(self, page_id, content, last_edited_time):
        """Process content through the crew and store in Qdrant"""
        if not content.strip():
            logger.info(f"No content to process for page {page_id}")
            return

        # Use the Knowledge Organizing Crew to process the content
        response = self.crew.kickoff(inputs={"document": content})

        if not isinstance(response.pydantic, ContextualizedChunks):
            logger.info(f"Did not receive any contextualized chunks for page: {page_id}")
            return

        # First, remove existing chunks for this page
        self.qdrant_storage.delete({"notion_page_id": page_id})

        # Store the processed chunks in Qdrant
        document_chunks: ContextualizedChunks = response.pydantic
        for chunk in document_chunks.chunks:
            formatted_input_data = f"{chunk.content}\n\n{chunk.context}"
            metadata = {
                "notion_page_id": page_id,
                "last_edited_time": last_edited_time,
                "chunk_context": chunk.context,
                "chunk_content": chunk.content,
            }
            self.qdrant_storage.save(formatted_input_data, metadata)

    def remove_deleted_pages_from_qdrant(self, current_pages):
        # Get all page IDs currently in Qdrant
        qdrant_page_ids = self.qdrant_storage.get_all_page_ids()

        # Determine which pages have been deleted
        current_page_ids = {page["id"] for page in current_pages}
        deleted_page_ids = qdrant_page_ids - current_page_ids

        # Remove deleted pages from Qdrant
        for page_id in deleted_page_ids:
            self.qdrant_storage.delete({"notion_page_id": page_id}) 