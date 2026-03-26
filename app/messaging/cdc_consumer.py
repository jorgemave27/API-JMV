"""
CDC CONSUMER (DEBEZIUM + KAFKA)

🔥 Integrado con TU proyecto:
- Usa elasticsearch_client.py (NO inventamos nada)
- Lee eventos reales de PostgreSQL WAL
- Sincroniza Elasticsearch automáticamente
"""

import json
import logging

from kafka import KafkaConsumer

from app.search import elasticsearch_client as es_client

logger = logging.getLogger(__name__)


class CDCConsumer:
    def __init__(self):
        self.consumer = KafkaConsumer(
            "dbserver1.public.items",
            bootstrap_servers="kafka:9092",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
            group_id="cdc-consumer-group",
        )

    def start(self):
        logger.info("🚀 CDC Consumer iniciado...")

        for message in self.consumer:
            try:
                payload = message.value.get("payload", {})

                op = payload.get("op")
                after = payload.get("after")
                before = payload.get("before")

                if op == "c":
                    self._handle_create(after)

                elif op == "u":
                    self._handle_update(after)

                elif op == "d":
                    self._handle_delete(before)

            except Exception as e:
                logger.error(f"❌ Error CDC: {e}")

    # =====================================================
    # HANDLERS
    # =====================================================

    def _build_fake_item(self, data: dict):
        """
        🔥 Adaptamos Debezium → modelo esperado por tu ES client
        """
        class FakeItem:
            pass

        item = FakeItem()
        item.id = data["id"]
        item.name = data.get("name")
        item.description = data.get("description")
        item.price = data.get("price")
        item.categoria_id = data.get("categoria_id")

        return item

    def _handle_create(self, data):
        if not data:
            return

        logger.info(f"🟢 CREATE {data['id']}")

        item = self._build_fake_item(data)
        es_client.index_item(item)

    def _handle_update(self, data):
        if not data:
            return

        logger.info(f"🟡 UPDATE {data['id']}")

        item = self._build_fake_item(data)
        es_client.update_item(item)

    def _handle_delete(self, data):
        if not data:
            return

        logger.info(f"🔴 DELETE {data['id']}")

        es_client.delete_item(data["id"])


if __name__ == "__main__":
    CDCConsumer().start()