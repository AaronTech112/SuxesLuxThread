# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Address

class RegisterForm(UserCreationForm):
    street      = forms.CharField(max_length=255, required=False)
    city        = forms.CharField(max_length=100, required=True)
    state       = forms.CharField(max_length=100, required=False)
    postal_code = forms.CharField(max_length=20,  required=True)
    country     = forms.CharField(max_length=100, required=True)

    class Meta:
        model  = CustomUser
        fields = [
            'first_name','last_name','username','email','phone_number',
            'password1','password2',
            # address fields are declared above, so not listed here
        ]

    def save(self, commit=True):
        # 1) save the user
        user = super().save(commit=commit)

        # 2) create and attach the address
        addr_data = {
          'street':      self.cleaned_data.get('street'),
          'city':        self.cleaned_data.get('city'),
          'state':       self.cleaned_data.get('state'),
          'postal_code': self.cleaned_data.get('postal_code'),
          'country':     self.cleaned_data.get('country'),
          'phone_number': self.cleaned_data.get('phone_number'),
        }
        address = Address.objects.create(**addr_data)
        user.address = address
        if commit:
            user.save()

        return user

class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = [ 'username', 'first_name', 'last_name', 'email', 'phone_number', ]
        
class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['street', 'city', 'state', 'postal_code', 'country','phone_number']
        widgets = {
            'street': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter street address'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter city'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter state'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter postal code'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter country'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Phone Number'}),
        }
        
class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = ['street', 'city', 'state', 'postal_code', 'country','phone_number']
        widgets = {
            'street': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter street address'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter city'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter state'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter postal code'}),
            'country': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter country'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Phone Number'}),
        }