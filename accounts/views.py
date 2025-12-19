from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import SignUpForm

def register(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created. You can log in now.")
            return redirect("login")
        messages.error(request, "Fix the errors below.")
    else:
        form = SignUpForm()
    return render(request, "auth/register.html", {"form": form})