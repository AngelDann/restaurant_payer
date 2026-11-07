import json

from channels.generic.websocket import AsyncWebsocketConsumer

# Realtime AI: use `from apps.ai_chat.agent import stream_ai_turn, ChatAgentDeps` and async callbacks
# to forward tokens to the socket (Celery is optional for background turns via `apps.ai_chat.tasks`).


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "invalid json"}))
            return
        message = data.get("message", "")
        await self.send(
            text_data=json.dumps({"type": "echo", "message": message}),
        )
