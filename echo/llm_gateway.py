# import logging
# import os
# from tenacity import retry, stop_after_attempt, wait_exponential
# from langchain_openai import ChatOpenAI
# from langchain_anthropic import ChatAnthropic
# from langchain_core.messages import BaseMessage
# from typing import List

# logger = logging.getLogger(__name__)

# # Primary: GPT-4o-mini (Cost-effective & Fast)
# primary_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
# # Fallback: Claude 3 Haiku (Different infrastructure, high reliability)
# fallback_llm = ChatAnthropic(model="claude-3-haiku-20240307", temperature=0)

# @retry(
#     stop=stop_after_attempt(3), 
#     wait=wait_exponential(multiplier=1, min=2, max=10),
#     reraise=True
# )
# async def safe_generate(messages: List[BaseMessage]):
#     """
#     Orchestrates LLM calls with automatic provider fallback.
#     """
#     try:
#         # Lead Touch: Ensure we use the async invoke
#         return await primary_llm.ainvoke(messages)
#     except Exception as e:
#         logger.warning(f"Primary LLM failed: {e}. Attempting fallback to Anthropic.")
#         try:
#             return await fallback_llm.ainvoke(messages)
#         except Exception as e2:
#             logger.error(f"Critical Failure: Both LLM providers failed. {e2}")
#             raise e2


import logging
import os
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage
from typing import List, AsyncGenerator

logger = logging.getLogger(__name__)

primary_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, streaming=True)
fallback_llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0, streaming=True)

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def safe_generate(messages: List[BaseMessage]):
    try:
        return await primary_llm.ainvoke(messages)
    except Exception as e:
        logger.warning(f"Primary LLM failed: {e}. Attempting fallback to Anthropic.")
        return await fallback_llm.ainvoke(messages)

async def safe_stream(messages: List[BaseMessage]) -> AsyncGenerator[str, None]:
    """
    Streams tokens from the primary LLM with a basic fallback check.
    """
    try:
        async for chunk in primary_llm.astream(messages):
            yield chunk.content
    except Exception as e:
        logger.warning(f"Primary streaming failed: {e}. Falling back to Anthropic stream.")
        async for chunk in fallback_llm.astream(messages):
            yield chunk.content
