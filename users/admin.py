from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("email", "first_name", "last_name", "phone", "email_verified", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_active", "email_verified")
    search_fields = ("email", "username", "first_name", "last_name", "phone")
    ordering = ("-date_joined",)
    readonly_fields = ("date_joined",)
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {"fields": ("email", "phone", "role", "profile_photo", "email_verified")}),
    )

    fieldsets = (
        (None, {"fields": ("email", "username", "password")} ),
        ("Personal info", {"fields": ("first_name", "last_name", "phone", "profile_photo")} ),
        ("Role & Verification", {"fields": ("role", "email_verified")} ),
        ("Permissions", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")} ),
        ("Important dates", {"fields": ("date_joined",)} ),
    )
