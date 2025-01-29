import logging
from email_assistant.crew import NotionQueryCrew
from email_assistant import models

logger = logging.getLogger(__name__)

class NotionQuerier:
    def __init__(self, embedder_config, qdrant_location, qdrant_api_key=None):
        self.crew = NotionQueryCrew(
            embedder_config=embedder_config,
            qdrant_location=qdrant_location,
            qdrant_api_key=qdrant_api_key
        ).crew()

    def ask_question(self, question: str) -> str:
        """
        Ask a question about the Notion knowledge base
        """
        try:
            response = self.crew.kickoff(inputs={"question": question})
            
            if not isinstance(response.pydantic, models.NotionAnswer):
                logger.warning("Unexpected response type from crew")
                return "Sorry, I couldn't find an answer to your question."
            
            answer = response.pydantic
            return f"{answer.answer}\n\nSources: {', '.join(answer.sources)}"
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return "Sorry, there was an error processing your question. Details: " + str(e)
