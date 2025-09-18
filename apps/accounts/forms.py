from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form__input'})
        self.fields['first_name'].widget.attrs.update({'class': 'form__input'})
        self.fields['last_name'].widget.attrs.update({'class': 'form__input'})
        self.fields['email'].widget.attrs.update({'class': 'form__input'})
        self.fields['password1'].widget.attrs.update({'class': 'form__input'})
        self.fields['password2'].widget.attrs.update({'class': 'form__input'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form__input'})
        self.fields['password'].widget.attrs.update({'class': 'form__input'})