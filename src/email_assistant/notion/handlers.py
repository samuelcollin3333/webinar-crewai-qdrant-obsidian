import logging
from notion_client import Client
from email_assistant.storage import QdrantStorage
from email_assistant.crew import KnowledgeOrganizingCrew
from email_assistant.models import ContextualizedChunks

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

    def sync_notion_to_qdrant(self):
        # Fetch all pages from the specified Teamspace
        pages = self.fetch_pages_from_teamspace()

        for page in pages:
            page_id = page["id"]
            last_edited_time = page["last_edited_time"]

            # Check if the page is already in Qdrant and if it needs updating
            if self.is_page_updated(page_id, last_edited_time):
                content = self.extract_content_from_page(page)
                self.process_and_store_content(page_id, content)

        # Remove pages from Qdrant that no longer exist in Notion
        self.remove_deleted_pages_from_qdrant(pages)

    def fetch_pages_from_teamspace(self):
        # Implement logic to fetch pages from the specified Teamspace
        # This might involve querying the Notion API with filters for the Teamspace
        return self.notion.databases.query(database_id="your_database_id").get("results", [])

    def is_page_updated(self, page_id, last_edited_time):
        # Implement logic to check if the page has been updated since the last sync
        # This could involve checking timestamps or maintaining a state file
        return True

    def extract_content_from_page(self, page):
        # Implement logic to extract and process content from a Notion page
        return "processed content"

    def process_and_store_content(self, page_id, content):
        # Use the Knowledge Organizing Crew to process the content
        response = self.crew.kickoff(inputs={"document": content})

        if not isinstance(response.pydantic, ContextualizedChunks):
            logger.info("Did not receive any contextualized chunks for page: %s", page_id)
            return

        # Store the processed chunks in Qdrant
        document_chunks: ContextualizedChunks = response.pydantic
        for chunk in document_chunks.chunks:
            formatted_input_data = f"{chunk.content}\n\n{chunk.context}"
            metadata = {
                "notion_page_id": page_id,
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