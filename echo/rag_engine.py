from typing import TypedDict, List, Annotated, Sequence
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from .llm_gateway import safe_generate
from .vectorstore import VectorStoreService
# from langchain_openai import OpenAIEmbeddings

from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.memory import MemorySaver

from langgraph.store.memory import InMemoryStore
from langgraph.graph.message import add_messages  

import re  
from .embeddings import embeddings
from .prompt import MAINPROMPT, BASEPROMPT, SYSTEM_PROMPT

# State Definition
class RAGState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    question: str # The original user input (e.g., "summarize this")
    expanded_query: str    # The optimized search string (e.g., "executive summary findings...")
    context: List[str]  # Chunks retrieved
    answer: str
    error: str
    is_redacted: bool
    document_id: str


def redact_pii(text: str) -> str:
    # Simple regex for emails
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    return re.sub(email_pattern, "[REDACTED_EMAIL]", text)

# --- Nodes ---

async def pii_guard_node(state: RAGState):
    """
    Redacts PII from the incoming question.
    """
    # Return both the current question and append it to the messages list
    return {
        "question": redact_pii(state["question"]), 
        "messages": [HumanMessage(content=state["question"])], # Log to history
        "is_redacted": True
    }

async def output_guard_node(state: RAGState):
    """
    Final scrub of the LLM answer before it hits the UI.
    """
    return {"answer": redact_pii(state["answer"])}


# --- Query Expansion Node ---
async def query_expansion_node(state: RAGState):
    """
    Step 1: Contextual Query Rewriting.
    Populates state["expanded_query"] for the retriever.
    """

    # Use your gateway's safe_generate
    rewrite_prompt = [
        SystemMessage(content=(
            "You are a search optimizer. Rewrite the user's question into a standalone "
            "search query for a vector database. Focus on key technical terms. "
            "If they ask for a summary, search for 'key findings, conclusions, and objectives'."
        )),
        *state.get("messages", []),
        HumanMessage(content=state["question"])
    ]
    
    try:
        response = await safe_generate(rewrite_prompt)
        return {"expanded_query": response.content}
    except Exception:
        # Fallback: if expansion fails, use the original question
        return {"expanded_query": state["question"]}

# --- Retrieve Node ---
async def retrieve_node(state: RAGState):
    """
    Step 2: Uses the expanded_query explicitly from the state.
    """
    vector_service = VectorStoreService(embeddings)
    
    # We pull the expanded version specifically
    search_term = state.get("expanded_query") or state["question"]
    
    docs = vector_service.search(search_term, k=6)
    context_chunks = [doc[0].page_content for doc in docs]
    
    return {"context": context_chunks}

async def retrieve_node(state: RAGState):
    """
    Node 1: Fetches context from Chroma.
    """
    vector_service = VectorStoreService(embeddings)
    
    # We retrieve k=5 for better grounding
    if state.get("document_id"):
        docs = vector_service.search(
            state["question"],
            k=5,
            metadata_filter={"document_id": state["document_id"]}
        )
    else:
        docs = vector_service.search(state["question"], k=5)
    
    # docs is a list of (Document, Score)
    context_chunks = [doc[0].page_content for doc in docs]
    
    return {"context": context_chunks}

async def generate_node(state: RAGState):
    """
    Node 2: Generates grounded response using the safe_generate gateway.
    """
    context_text = "\n\n".join(state["context"])
    
    system_prompt = SystemMessage(content=("{SYSTEM_PROMPT}") )

    user_message = HumanMessage(content=state["question"])

    # Combine History + System Prompt
    llm_input = [system_prompt] + state["messages"] + [user_message]
    
    # Calls the gateway with retry logic
    #response = await safe_generate([llm_input, user_message])
    response = await safe_generate(llm_input)
    
    return {"answer": response.content, "messages": [user_message, response]}


def compile_workflow():
    workflow = StateGraph(RAGState)

    # Define Nodes
    workflow.add_node("pii_pre_check", pii_guard_node)
    workflow.add_node("expand_query", query_expansion_node) # <--- New Node
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("pii_post_check", output_guard_node)

    # Define Edges
    workflow.set_entry_point("pii_pre_check")
    # workflow.add_edge("pii_pre_check", "retrieve")
    workflow.add_edge("pii_pre_check", "expand_query") # <--- Route to expansion
    workflow.add_edge("expand_query", "retrieve")     # <--- Then to retrieval

    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "pii_post_check")
    workflow.add_edge("pii_post_check", END)

    graph = workflow.compile(
        checkpointer=MemorySaver(),   # per-thread state
        store=InMemoryStore()           # cross-thread state
    )
    return graph


# Singleton instance for the app
rag_graph = compile_workflow()
