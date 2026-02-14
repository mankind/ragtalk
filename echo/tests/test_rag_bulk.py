import os, re
import shutil
import asyncio
from django.test import TransactionTestCase, override_settings

from django.conf import settings
from langchain_core.messages import SystemMessage, HumanMessage

from echo.rag_engine import rag_graph
from echo.llm_gateway import safe_generate

# Define a specific directory for test files
TEST_MEDIA_ROOT = os.path.join(settings.BASE_DIR, 'media', 'test_media')

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class RAGBulkEvaluationTest(TransactionTestCase):
    """
    Bulk evaluates the RAG system across multiple files and golden pairs.
    """
    reset_sequences = True

    def setUp(self):
        # Ensure the directory exists
        if not os.path.exists(TEST_MEDIA_ROOT):
            os.makedirs(TEST_MEDIA_ROOT)
        
        self.config = {
            "configurable": {
                "thread_id": "test_thread"
            }
        }
        # Define Golden Pairs: (Question, Expected Fact to check for)
       
        self.golden_pairs = [
            ("Who are the authors of the GPT4All technical report?", "Yuvanesh Anand, Zach Nussbaum, Brandon Duderstadt, Benjamin Schmidt, Andriy Mulyar"),
            ("What is the main purpose of GPT4All?", "chatbot trained over a massive curated corpus of assistant interactions"),
            ("How many prompt-response pairs were collected for training?", "437,605 high-quality prompt-response pairs in final subset"),
            ("What datasets were used to collect the initial prompts?", "chip2 subset of LAION OIG, Stackoverflow, Bigscience/P3"),
            ("What were the GPU and API costs to train GPT4All?", "$800 in GPU costs and $500 in OpenAI API spend"),
            ("Which model was fine-tuned to create GPT4All?", "LLaMA 7B with LoRA on curated dataset"),
            ("What evaluation method was used to measure GPT4All’s performance?", "human evaluation from Self-Instruct paper comparing ground truth perplexity")
        ]


    def tearDown(self):
        """
        Cleans up the test media folder completely after the test run.
        """
        if os.path.exists(TEST_MEDIA_ROOT):
            shutil.rmtree(TEST_MEDIA_ROOT)

    async def run_evaluation(self, question, state):
        """
        Internal helper to score the RAG output via LLM-as-a-Judge.
        """
        context_str = "\n".join(state.get("context", []))
        answer = state.get("answer", "")
        
        eval_prompt = [
            SystemMessage(content="You are a strict QA auditor. Rate the response from 0.0 to 1.0."),
            HumanMessage(content=f"CONTEXT: {context_str}\nQUESTION: {question}\nANSWER: {answer}\n\n"
                                 f"Score based on: 1. Faithfulness to context 2. Relevance to question.")
        ]
        
        response = await safe_generate(eval_prompt)
        try:
            raw = response.content.strip()
            print("[Judge Raw]:", raw)

            match = re.search(r"\d*\.?\d+", raw)
            return float(match.group()) if match else 0.0
        except ValueError:
            return 0.0

    async def test_bulk_rag_performance(self):
        """
        Main test loop: Iterates through files and questions.
        """
        # 1. Check if we have files to test
        files = [f for f in os.listdir(TEST_MEDIA_ROOT) if f.endswith('.pdf')]
        if not files:
            print("--- No test PDFs found in media/test_media. Skipping bulk test. ---")
            return

        total_scores = []

        for file_name in files:
            print(f"\n>>> Evaluating File: {file_name}")
            
            for question, _ in self.golden_pairs:
                # Run the Graph
                config = {"configurable": {"thread_id": f"test_{file_name}"}}
                state = await rag_graph.ainvoke({"question": question}, config)

                # LOG THE EXPANDED QUERY (Requirement #3)
                expanded = state.get("expanded_query", "N/A (Expansion Node Failed)")
                print(f"  [Q]: {question}")
                print(f"  [Expanded Search]: {expanded}")

                # Verify expansion actually happened or defaulted
                self.assertTrue(len(expanded) > 0, "Expanded query should not be empty.")

                # Score it
                score = await self.run_evaluation(question, state)
                total_scores.append(score)
                print(f"  [Score]: {score}")

        # Final Report
        avg_score = sum(total_scores) / len(total_scores) if total_scores else 0
        print(f"\n--- FINAL BULK SCORE: {avg_score:.2f} ---")
        self.assertGreaterEqual(avg_score, 0.7, "Average RAG quality fell below threshold!")
