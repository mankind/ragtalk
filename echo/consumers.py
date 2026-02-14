
import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer

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
