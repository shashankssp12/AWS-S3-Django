from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    storage_quota = models.BigIntegerField(default=1073741824)  # Default 1GB in bytes
    
    def get_used_storage(self):
        """Calculate used storage by summing all file sizes"""
        return self.user.files.aggregate(total=models.Sum('size'))['total'] or 0
    
    def get_available_storage(self):
        """Calculate remaining available storage"""
        return self.storage_quota - self.get_used_storage()

class Folder(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='folders')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Ensuring folder names are unique within the same parent folder for the same user
        unique_together = ('owner', 'parent', 'name')
    
    def __str__(self):
        return self.name
        
    def get_path(self):
        """Get the full path of this folder"""
        if self.parent:
            return f"{self.parent.get_path()}/{self.name}"
        return self.name