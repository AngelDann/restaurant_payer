from __future__ import annotations

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class TableOrderConsumer(AsyncWebsocketConsumer):
    """Real-time WebSocket updates for a specific table's bill & restaurant dashboard."""

    async def connect(self):
        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.table_number = self.scope["url_route"]["kwargs"]["table_number"]
        self.group_name = f"table_{self.slug}_{self.table_number}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def order_updated(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "order_updated",
                    "order_id": event.get("order_id"),
                    "status": event.get("status"),
                    "amount_paid": event.get("amount_paid"),
                    "amount_remaining": event.get("amount_remaining"),
                }
            )
        )
