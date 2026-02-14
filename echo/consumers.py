
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from langchain_core.messages import HumanMessage, SystemMessage
from .llm_gateway import safe_stream
from .rag_engine import rag_graph, redact_pii


class DocumentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Join the global documents group
        await self.channel_layer.group_add("documents", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("documents", self.channel_name)

    # These methods match the 'type' in group_send
    async def document_indexed(self, event):
        await self.send(text_data=json.dumps(event))

    async def document_failed(self, event):
        await self.send(text_data=json.dumps(event))


##############
# Chat
#############

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive(self, text_data):
        # user_input = json.loads(text_data).get('message')
        message_data = json.loads(text_data)
        user_input = message_data.get('message')
        document_id = message_data.get('document_id')
        # thread_id = self.channel_name # Pass from UI in production

        thread_id = self.scope.get("session").session_key

        # Fire and forget to keep the socket responsive
        asyncio.create_task(self.stream_openai_response(user_input, thread_id, document_id))

    
    async def stream_openai_response(self, message, thread_id, document_id=None):
        config = {"configurable": {"thread_id": thread_id}}

        full_content = ""

        async for event in rag_graph.astream_events(
            {"question": message, "document_id": document_id},
            config,
            version="v1",
        ):
            # We only care about LLM token streaming events
            if event["event"] == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    clean_token = redact_pii(token)
                    full_content += clean_token
                    await self.send(
                        text_data=json.dumps({"text": clean_token})
                    )

      