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


# State Definition
class RAGState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    question: str
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
    
    system_prompt = SystemMessage(content=(
        "You are a professional Document Assistant. "
        "Answer the question ONLY using the provided context. "
        "If the answer is not in the context, say 'I cannot find this in the documents.' "
        f"\n\nCONTEXT:\n{context_text}"
    ))
    
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
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("pii_post_check", output_guard_node)

    # Define Edges
    workflow.set_entry_point("pii_pre_check")
    workflow.add_edge("pii_pre_check", "retrieve")
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
