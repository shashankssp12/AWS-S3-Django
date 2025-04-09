from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login,  logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import UserProfile

# Create your views here.
def register(request):
    if request.method == 'POST': 
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create a UserProfile for the new user
            UserProfile.objects.create(user=user)
            # Log the user in after rergistration
            login(request, user)
            messages.success(request, "Registration Successful")
            return redirect('dashboard')
        else: 
            messages.error(request, "Registration failed. Please correct the errors.")
    else:
        # this is to display the blank form to the user, GET request
        form = UserCreationForm()
    return render(request, 's3connector/register.html', {'form':form})     
        
def login_view(request):
    """Handle user login"""
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "You have successfully logged in!")
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 's3connector/login.html', {'form': form})

def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')
    
# Dashboard Views
@login_required
def dashboard_view(request):
    """Display user dashboard with storage usage and files"""
    # Get user profile for storage info
    profile = request.user.profile
    used_storage = profile.get_used_storage()
    total_storage = profile.storage_quota
    storage_percentage = (used_storage / total_storage) * 100 if total_storage > 0 else 0
    
    # Get user's files and folders
    files = request.user.files.all().order_by('-uploaded_at')
    folders = request.user.folders.filter(parent=None).order_by('name')
    
    context = {
        'files': files,
        'folders': folders,
        'used_storage': used_storage,
        'total_storage': total_storage,
        'storage_percentage': storage_percentage,
    }
    return render(request, 's3connector/dashboard.html', context)

# File Upload View
@login_required
def upload_file_view(request):
    """Handle file uploads"""
    if request.method == 'POST':
        file = request.FILES.get('file')
        folder_id = request.POST.get('folder')
        
        if not file:
            messages.error(request, "No file was selected.")
            return redirect('dashboard')
        
        # Check if user has enough storage
        profile = request.user.profile
        if file.size > profile.get_available_storage():
            messages.error(request, "Not enough storage available.")
            return redirect('dashboard')
        
        # Get the selected folder (if any)
        folder = None
        if folder_id:
            try:
                folder = request.user.folders.get(id=folder_id)
            except:
                messages.warning(request, "Selected folder not found.")
        
        # Upload file to S3
        from .s3utils import S3Uploader
        uploader = S3Uploader()
        result = uploader.upload(file, file.name)
        
        if result['success']:
            # Create File record in database
            from .models import File
            
            # Determine file category based on content type
            content_type = result['file_info']['content_type']
            category = 'other'
            if content_type.startswith('image/'):
                category = 'image'
            elif content_type.startswith('video/'):
                category = 'video'
            elif content_type.startswith('audio/'):
                category = 'audio'
            elif 'pdf' in content_type or 'document' in content_type or 'spreadsheet' in content_type:
                category = 'document'
            
            # Create the file record
            File.objects.create(
                name=result['file_info']['key'].split('/')[-1],
                original_name=file.name,
                s3_key=result['file_info']['key'],
                size=result['file_info']['size_bytes'],
                content_type=content_type,
                category=category,
                owner=request.user,
                folder=folder
            )
            
            messages.success(request, f"File {file.name} uploaded successfully!")
        else:
            messages.error(request, f"Error uploading file: {result['message']}")
        
        return redirect('dashboard')
    
    # GET request - show upload form
    folders = request.user.folders.all()
    return render(request, 's3connector/upload.html', {'folders': folders})

@login_required
def file_list_view(request, category=None):
    """List files, optionally filtered by category"""
    files_query = request.user.files.all()
    
    if category and category != 'all':
        files_query = files_query.filter(category=category)
    
    files = files_query.order_by('-uploaded_at')
    
    context = {
        'files': files,
        'category': category or 'all',
        'categories': [choice[0] for choice in File.CATEGORY_CHOICES]
    }
    return render(request, 's3connector/file_list.html', context)

@login_required
def file_detail_view(request, file_id):
    """View details of a specific file"""
    try:
        file = request.user.files.get(id=file_id)
        context = {'file': file}
        return render(request, 's3connector/file_detail.html', context)
    except:
        messages.error(request, "File not found.")
        return redirect('file_list')

@login_required
def delete_file_view(request, file_id):
    """Delete a file"""
    try:
        file = request.user.files.get(id=file_id)
        
        # Delete from S3
        from .s3utils import delete_file_from_s3
        s3_key = file.s3_key.split('/')[-1]  # Get just the filename without the folder
        
        if delete_file_from_s3(s3_key):
            # Delete from database
            file.delete()
            messages.success(request, "File deleted successfully.")
        else:
            messages.error(request, "Error deleting file from storage.")
            
    except Exception as e:
        messages.error(request, f"Error deleting file: {str(e)}")
        
    return redirect('file_list')

@login_required
def download_file_view(request, file_id):
    """Generate download URL and redirect"""
    try:
        file = request.user.files.get(id=file_id)
        download_url = file.get_download_url()
        
        if download_url:
            return redirect(download_url)
        else:
            messages.error(request, "Error generating download link.")
            return redirect('file_detail', file_id=file_id)
    except:
        messages.error(request, "File not found.")
        return redirect('file_list')
    
# Folder Management Views
@login_required
def create_folder_view(request):
    """Create a new folder"""
    if request.method == 'POST':
        folder_name = request.POST.get('folder_name')
        parent_id = request.POST.get('parent_folder')
        
        if not folder_name:
            messages.error(request, "Please provide a folder name.")
            return redirect('dashboard')
        
        # Get parent folder if specified
        parent = None
        if parent_id:
            try:
                parent = request.user.folders.get(id=parent_id)
            except:
                messages.warning(request, "Parent folder not found.")
        
        # Create the folder
        try:
            from .models import Folder
            Folder.objects.create(
                name=folder_name,
                owner=request.user,
                parent=parent
            )
            messages.success(request, f"Folder '{folder_name}' created successfully!")
        except Exception as e:
            messages.error(request, f"Error creating folder: {str(e)}")
        
        return redirect('dashboard')
    
    # GET request - show folder creation form
    folders = request.user.folders.all()
    return render(request, 's3connector/create_folder.html', {'folders': folders})

@login_required
def folder_view(request, folder_id):
    """View contents of a folder"""
    try:
        folder = request.user.folders.get(id=folder_id)
        files = folder.files.all().order_by('-uploaded_at')
        subfolders = folder.subfolders.all().order_by('name')
        
        context = {
            'folder': folder,
            'files': files,
            'subfolders': subfolders,
        }
        return render(request, 's3connector/folder.html', context)
    except:
        messages.error(request, "Folder not found.")
        return redirect('dashboard')

@login_required
def delete_folder_view(request, folder_id):
    """Delete a folder"""
    try:
        folder = request.user.folders.get(id=folder_id)
        
        # Check if folder has files
        if folder.files.exists():
            messages.error(request, "Cannot delete folder that contains files.")
            return redirect('folder', folder_id=folder_id)
        
        # Check if folder has subfolders
        if folder.subfolders.exists():
            messages.error(request, "Cannot delete folder that contains subfolders.")
            return redirect('folder', folder_id=folder_id)
        
        folder.delete()
        messages.success(request, "Folder deleted successfully.")
        return redirect('dashboard')
    except:
        messages.error(request, "Folder not found or cannot be deleted.")
        return redirect('dashboard')