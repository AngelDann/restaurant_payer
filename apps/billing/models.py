from django.db import models


class StripeWebhookEvent(models.Model):
    """Stores Stripe event ids (evt_...) for webhook idempotency."""

    event_id = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.event_id
