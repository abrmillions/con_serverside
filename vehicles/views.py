from rest_framework import viewsets, permissions, serializers
from .models import Vehicle
from .serializers import VehicleSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.owner == request.user


class VehicleViewSet(viewsets.ModelViewSet):
    serializer_class = VehicleSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Vehicle.objects.all()
        return Vehicle.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        # Enforce: one vehicle registration per user account (email)
        if Vehicle.objects.filter(owner=user).exists():
            raise serializers.ValidationError({"detail": "You have already registered a vehicle with this account."})
        serializer.save(owner=user)
