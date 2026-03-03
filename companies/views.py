from rest_framework import viewsets, permissions
from .models import Company
from .serializers import CompanySerializer


class IsCompanyManagerOrStaff(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        return obj.contact_person == request.user

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class CompanyViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySerializer
    permission_classes = [IsCompanyManagerOrStaff]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Company.objects.all()
        return Company.objects.filter(contact_person=user)
