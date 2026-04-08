"""Admin registrations for django_cognito_m2m."""

from __future__ import annotations

from django.contrib import admin

from django_cognito_m2m.models import ServiceClientActivity


@admin.register(ServiceClientActivity)
class ServiceClientActivityAdmin(admin.ModelAdmin):
    """Admin view for service client activity records."""

    list_display = ("client_id", "first_seen_at", "last_seen_at")
    search_fields = ("client_id",)
    ordering = ("client_id",)
