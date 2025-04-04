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
    
    
    
    # def login(request):
# def logout(request):