from django import forms
from .models import Product

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["category", "name", "description", "price", "stock", "image", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "required": True}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01", "required": True}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": "0", "required": True}),
            "category": forms.Select(attrs={"class": "form-select", "required": True}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_image(self):
        img = self.cleaned_data.get("image")
        if not img:
            return img
        if img.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Image must be <= 2MB.")
        if not img.content_type.startswith("image/"):
            raise forms.ValidationError("File must be an image.")
        return img