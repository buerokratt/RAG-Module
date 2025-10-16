import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import anthropic

load_dotenv()


class MockQdrantRetriever:
    """Mock implementation of Qdrant vector database with predefined test data."""

    def __init__(self):
        self.knowledge_base: Dict[str, List[str]] = {
            "pension": [
                "In 2021, the pension will become more flexible. People will be able to choose the most suitable time for their retirement, partially withdraw their pension or stop payment of their pension if they wish, in effect creating their own personal pension plan.",
                "Starting in 2027, retirement age calculations will be based on the life expectancy of 65-year-olds. The pension system will thus be in line with demographic developments.",
                "From 2021, the formula for the state old-age pension will be upgraded - starting in 2021, we will start collecting the so-called joint part.",
            ],
            "family_benefits": [
                "In 2021, a total of approximately 653 million euros in benefits were paid to families. Approximately 310 million euros for family benefits; Approximately 280 million euros for parental benefit.",
                "The Estonian parental benefit system is one of the most generous in the world, both in terms of the length of the period covered by the benefit and the amount of the benefit.",
                "23,687 families and 78,296 children receive support for families with many children, including 117 families with seven or more children.",
            ],
            "single_parent": [
                "8,804 parents and 1,0222 children receive single parent support.",
                "Single-parent (mostly mother) families are at the highest risk of poverty, of whom 5.3% live in absolute poverty and 27.3% in relative poverty.",
                "Since January 2022, the Ministry of Social Affairs has been looking for solutions to support single-parent families.",
            ],
            "train_tickets": [
                "Ticket refund is only possible if at least 60 minutes remain until the departure of the trip.",
                "The ticket cost is refunded to the Elron travel card without service charge only if the refund request is submitted through the Elron homepage refund form.",
                "If ticket refund is requested to a bank account, a service fee of 1 euro is deducted from the refundable amount.",
            ],
            "health_cooperation": [
                "Europe must act more jointly and in a more coordinated way to stop the spread of health-related misinformation, said Estonia's Minister of Social Affairs, Karmen Joller.",
                "Estonian Minister of Social Affairs Karmen Joller and Ukrainian Minister of Health Viktor Liashko today signed the next stage of a health cooperation agreement.",
                "The aim of the agreement is to reinforce health collaboration, support Ukraine's healthcare system recovery.",
            ],
        }

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """Mock hybrid vector + BM25 search and re-ranking."""
        query_lower = query.lower()

        # Simple keyword matching for mock retrieval
        relevant_contexts: list[str] = []

        # Check for topic keywords in query (expanded multilingual support)
        topic_keywords = {
            "pension": [
                "pension",
                "pensioni",
                "pensionieaarvutus",
                "retirement",
                "vanaduspension",
                "пенсия",
                "пенсионный",
                "возраст",
                "расчеты",
                "гибк",
            ],
            "family_benefits": [
                "family",
                "benefit",
                "toetus",
                "pere",
                "lapsetoetus",
                "parental",
                "семья",
                "пособие",
                "семейный",
                "родитель",
                "дети",
                "поддержка",
                "palju",
                "raha",
                "maksti",
                "peredele",
            ],
            "single_parent": [
                "single",
                "parent",
                "üksikvanem",
                "poverty",
                "vaesus",
                "одиночек",
                "родител",
                "бедност",
                "поддержка",
                "семей",
            ],
            "train_services": [
                "train",
                "ticket",
                "pilet",
                "elron",
                "tagastamine",
                "refund",
                "поезд",
                "билет",
                "возврат",
                "отправлени",
                "минут",
                "расписани",
                "sõiduplaan",
                "teated",
                "уведомлени",
            ],
            "health_cooperation": [
                "health",
                "cooperation",
                "karmen",
                "joller",
                "ukraine",
                "misinformation",
                "здравоохранени",
                "сотрудничеств",
                "соглашени",
                "украин",
                "дезинформаци",
                "tervis",
                "koostöö",
                "leping",
                "innovation",
                "инноваци",
            ],
            "contact_information": [
                "ministry",
                "contact",
                "ministeerium",
                "newsletter",
                "uudiskiri",
                "министерств",
                "контакт",
                "социальн",
                "данные",
                "адрес",
            ],
        }

        # Find matching topics
        matching_topics: list[str] = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                matching_topics.append(topic)

        # Get contexts from matching topics
        for topic in matching_topics:
            if topic in self.knowledge_base:
                relevant_contexts.extend(self.knowledge_base[topic])

        # If no specific match, return some general contexts
        if not relevant_contexts:
            relevant_contexts = (
                self.knowledge_base["pension"][:2]
                + self.knowledge_base["family_benefits"][:1]
            )

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_contexts: list[str] = []
        for context in relevant_contexts:
            if context not in seen:
                seen.add(context)
                unique_contexts.append(context)

        return unique_contexts[:top_k]


class DummyLLMOrchestrator:
    """Main orchestrator that handles the complete RAG pipeline."""

    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        self.retriever = MockQdrantRetriever()

        if provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        else:
            raise ValueError("Provider must be 'anthropic' or 'openai'")

    def _generate_with_anthropic(self, prompt: str) -> str:
        """Generate response using Anthropic Claude."""
        try:
            response = self.client.messages.create(  # type: ignore
                model="claude-3-7-sonnet-20250219",
                max_tokens=1024,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text  # type: ignore
        except Exception as e:
            return f"Error generating response with Anthropic: {str(e)}"

    def _mock_nvidia_nemo_guardrail(self, response: str) -> bool:
        """Mock NVIDIA NeMO output guardrail check."""
        # Simple mock: reject responses that are too short or contain error messages
        if len(response) < 10 or "error" in response.lower():
            return False
        return True

    def generate_response(
        self, question: str, include_contexts: bool = False
    ) -> Dict[str, Any]:
        """
        Complete RAG pipeline: retrieve contexts and generate response.

        Args:
            question: User's question
            include_contexts: Whether to include retrieval contexts in response

        Returns:
            Dictionary containing response and optionally contexts
        """
        # Step 1: Retrieve contexts using hybrid search
        contexts = self.retriever.retrieve(question, top_k=3)

        # Step 2: Construct prompt with retrieved contexts
        context_text = "\n\n".join(contexts)
        prompt = f"""Based on the following context information, please answer the question accurately and helpfully.

Context:
{context_text}

Question: {question}

Answer:"""

        # Step 3: Generate response with LLMs
        max_attempts = 2
        response: str = ""
        for attempt in range(max_attempts):
            if self.provider == "anthropic":
                response: str = self._generate_with_anthropic(prompt)
            else:
                response: str = "Unsupported provider."
            # Step 4: Check with NVIDIA NeMO guardrail
            if self._mock_nvidia_nemo_guardrail(response):
                break
            elif attempt == max_attempts - 1:
                response = (
                    "I'm sorry, I cannot provide a suitable response at this time."
                )

        result: dict[str, str | list[str]] = {"response": response}
        if include_contexts:
            result["retrieval_context"] = contexts

        return result


# API endpoint functions for testing
def create_llm_orchestrator(provider: str = "anthropic") -> DummyLLMOrchestrator:
    """Factory function to create LLM orchestrator."""
    return DummyLLMOrchestrator(provider)


def process_query(
    question: str, provider: str = "anthropic", include_contexts: bool = False
) -> Dict[str, Any]:
    """
    Process a single query through the RAG pipeline.

    Args:
        question: User's question
        provider: LLM provider ('anthropic' or 'openai')
        include_contexts: Whether to include retrieval contexts

    Returns:
        Dictionary with response and optionally contexts
    """
    orchestrator = create_llm_orchestrator(provider)
    return orchestrator.generate_response(question, include_contexts)
