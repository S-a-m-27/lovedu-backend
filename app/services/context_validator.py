import logging
from typing import Optional, List, Dict
from app.models.chat import AssistantType

logger = logging.getLogger(__name__)

class ContextValidator:
    """
    Validates if user questions are within the conversation context
    """
    
    @staticmethod
    def is_context_related(
        message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        assistant_id: AssistantType = AssistantType.typeX
    ) -> bool:
        """
        Check if the message is related to the conversation context
        
        Args:
            message: Current user message
            conversation_history: Previous conversation messages
            assistant_id: Type of assistant
            
        Returns:
            bool: True if message seems context-related, False otherwise
        """
        # If no conversation history, any question is valid (new conversation)
        if not conversation_history or len(conversation_history) == 0:
            logger.debug("   No conversation history - message is context-valid (new conversation)")
            return True
        
        # Extract key topics from conversation history
        context_topics = ContextValidator._extract_context_topics(conversation_history)
        message_lower = message.lower()
        
        # Check if message contains context-related keywords
        context_related = any(
            topic.lower() in message_lower or message_lower in topic.lower()
            for topic in context_topics
            if len(topic) > 3  # Ignore very short topics
        )
        
        # Also check for continuation phrases
        continuation_phrases = [
            "what about", "tell me more", "explain", "how", "why", "can you",
            "what is", "what are", "describe", "elaborate", "clarify"
        ]
        has_continuation = any(phrase in message_lower for phrase in continuation_phrases)
        
        is_valid = context_related or has_continuation
        
        logger.debug(f"   Context validation - Related: {context_related}, Has continuation: {has_continuation}, Valid: {is_valid}")
        
        return is_valid
    
    @staticmethod
    def _extract_context_topics(conversation_history: List[Dict[str, str]]) -> List[str]:
        """
        Extract key topics from conversation history
        """
        topics = []
        
        for msg in conversation_history:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Extract first few words as potential topics
                words = content.split()[:10]  # First 10 words
                topics.extend(words)
            elif msg.get("role") == "assistant":
                content = msg.get("content", "")
                # Extract key phrases from assistant responses
                words = content.split()[:15]  # First 15 words
                topics.extend(words)
        
        # Remove duplicates and return
        unique_topics = list(set(topics))
        logger.debug(f"   Extracted {len(unique_topics)} context topics")
        
        return unique_topics
    
    @staticmethod
    def get_out_of_context_response(assistant_id: AssistantType) -> str:
        """
        Get a polite response when question is out of context
        """
        responses = {
            AssistantType.typeX: (
                "I apologize, but I need more information to provide accurate guidance. "
                "Could you please clarify your question about Kuwait University regulations or procedures? "
                "To be completely sure, please confirm this information with Kuwait University or your college/department."
            ),
            AssistantType.references: (
                "I apologize, but I need more information to provide accurate guidance about your student rights. "
                "Could you please clarify your question about Kuwait University regulations or student rights? "
                "To be completely sure, please confirm this information with Kuwait University or the relevant college/department."
            ),
            AssistantType.academicReferences: (
                "I apologize, but I need more information to format your reference correctly. "
                "Could you please provide the reference details you'd like me to format in APA 7th edition? "
                "I'm here to help format academic references according to Kuwait University guidelines."
            ),
            AssistantType.therapyGPT: (
                "I apologize, but I need more information to share relevant success stories. "
                "Could you please tell me about your situation or what kind of success story you're looking for? "
                "I'm here to share documented success stories to support students."
            ),
            AssistantType.whatsTrendy: (
                "I apologize, but I need more information to find relevant trends and events for you. "
                "Could you please clarify what type of events or trends you're interested in? "
                "(e.g., tech, business, culture, university events). "
                "Please verify event details and registration information through the official event organizer or platform."
            )
        }
        
        return responses.get(assistant_id, responses[AssistantType.typeX])

