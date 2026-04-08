"""Database models for django_cognito_m2m."""

from __future__ import annotations

from django.db import models


class ServiceClientActivity(models.Model):
    """Track first and most recent successful authentication per client id."""

    client_id = models.CharField(max_length=255, unique=True, db_index=True)
    first_seen_at = models.DateTimeField()
    last_seen_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["client_id"]
        verbose_name = "service client activity"
        verbose_name_plural = "service client activity"

    def __str__(self) -> str:
        return self.client_id
