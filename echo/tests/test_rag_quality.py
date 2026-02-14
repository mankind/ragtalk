import asyncio, re
from django.test import TransactionTestCase
from echo.rag_engine import rag_graph
from echo.llm_gateway import safe_generate
from langchain_core.messages import HumanMessage, SystemMessage

class RAGQualityTest(TransactionTestCase):
    """
    Evaluates the 'Triad' of RAG: Faithfulness, Relevance, and Groundedness.
    """

    def setUp(self):
        
        self.config = {
            "configurable": {
                "thread_id": "test_thread"
            }
        }

    async def get_llm_score(self, rubric: str, context: str, question: str, answer: str) -> float:
        """
        Uses the LLM-as-a-Judge pattern to score the RAG output.
        """
        eval_prompt = [
            SystemMessage(content=f"You are a strict grader. Rate the following based on this rubric: {rubric}"),
            HumanMessage(content=f"CONTEXT: {context}\nQUESTION: {question}\nANSWER: {answer}\n\n"
                                 f"Provide a score between 0.0 and 1.0. Output ONLY the number.")
        ]
        response = await safe_generate(eval_prompt)
        try:
            raw = response.content.strip()
            print("[Judge Raw]:", raw)

            match = re.search(r"\d*\.?\d+", raw)
            return float(match.group()) if match else 0.0

        except ValueError:
            return 0.0

    async def test_rag_groundedness_and_relevance(self):
        # 1. Setup the scenario
        question = "Who are the authors of the paper?"
        thread_id = "eval_user_123"
        config = {"configurable": {"thread_id": thread_id}}

        # 2. Run the actual RAG workflow
        state = await rag_graph.ainvoke({"question": question}, config)
        
        context_str = "\n".join(state["context"])
        answer = state["answer"]

        # 3. Evaluate Faithfulness (Groundedness)
        # Rubric: Does the answer contain info NOT found in the context?
        faithfulness_score = await self.get_llm_score(
            "Is the answer derived ONLY from the context provided? 1.0 if perfect, 0.0 if hallucinated.",
            context_str, question, answer
        )

        # 4. Evaluate Answer Relevance
        # Rubric: Does the answer actually address the user's question?
        relevance_score = await self.get_llm_score(
            "Does the answer directly address the user's question? 1.0 if perfect, 0.0 if irrelevant.",
            context_str, question, answer
        )

        # 5. Assertions
        print(f"\n[EVAL] Faithfulness: {faithfulness_score} | Relevance: {relevance_score}")
        
        self.assertGreaterEqual(faithfulness_score, 0.8, "The AI is hallucinating information not in the PDF!")
        self.assertGreaterEqual(relevance_score, 0.8, "The AI's answer is not relevant to the user's question!")


    async def test_rag_negative_case(self):
        # Ask something completely unrelated to the uploaded PDFs
        question = "What is the recipe for chocolate cake?"
        state = await rag_graph.ainvoke({"question": question}, self.config)
        
        # We expect high faithfulness (because it shouldn't claim the PDF has recipes)
        # but the answer should be the 'I cannot find this' string.
        self.assertIn("I cannot find this in the documents", state["answer"])
