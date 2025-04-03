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
    
    
class File(models.Model):
    CATEGORY_CHOICES = [
        ('image', 'Image'),
        ('document', 'Document'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255)  # Original filename before deduplication
    s3_key = models.CharField(max_length=1024)  # Full path in S3
    size = models.BigIntegerField()  # Size in bytes
    content_type = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='files')
    folder = models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True, related_name='files')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    def get_download_url(self):
        """Generate a download URL for this file"""
        from s3connector.s3utils import create_download_link
        return create_download_link(self.s3_key)
    
class FilePermission(models.Model):
    PERMISSION_CHOICES = [
        ('private', 'Private'),
        ('public', 'Public'),
        ('shared', 'Shared with specific users')
    ]
    
    file = models.OneToOneField(File, on_delete=models.CASCADE, related_name='permission')
    permission_type = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default='private')
    shared_users = models.ManyToManyField(User, blank=True, related_name='shared_files')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def can_access(self, user):
        """Check if a user can access this file"""
        # Owner always has access
        if user == self.file.owner:
            return True
            
        # Check based on permission type
        if self.permission_type == 'public':
            return True
        elif self.permission_type == 'shared':
            return user in self.shared_users.all()
            
        # Private - only owner can access
        return False