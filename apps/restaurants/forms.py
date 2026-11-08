from __future__ import annotations

from django import forms
from django.utils.text import slugify

from apps.restaurants.models import MenuCategory, MenuItem, Restaurant, Table


class RestaurantForm(forms.ModelForm):
    slug = forms.SlugField(
        max_length=150,
        required=False,
        help_text="Identificador único para enlaces. Se genera automáticamente si se deja vacío.",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "ej. plav-roma-norte"}
        ),
    )

    class Meta:
        model = Restaurant
        fields = [
            "name",
            "slug",
            "tagline",
            "address",
            "logo_url",
            "cover_image_url",
            "google_maps_review_url",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nombre del restaurante"}
            ),
            "tagline": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Eslogan o tipo de cocina"}
            ),
            "address": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Dirección completa"}
            ),
            "logo_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://..."}
            ),
            "cover_image_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://..."}
            ),
            "google_maps_review_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://g.page/r/..."}
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        slug = cleaned_data.get("slug")

        if not slug and name:
            base_slug = slugify(name)
            if not base_slug:
                base_slug = "restaurante"
            candidate = base_slug
            counter = 2
            qs = Restaurant.objects.filter(slug=candidate)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            while qs.exists():
                candidate = f"{base_slug}-{counter}"
                counter += 1
                qs = Restaurant.objects.filter(slug=candidate)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
            cleaned_data["slug"] = candidate
            self.cleaned_data["slug"] = candidate
        elif slug:
            qs = Restaurant.objects.filter(slug=slug)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("slug", "Ya existe un restaurante con este identificador único (slug).")

        return cleaned_data


class TableForm(forms.ModelForm):
    class Meta:
        model = Table
        fields = ["number", "label"]
        widgets = {
            "number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej: 1, 26, T1"}
            ),
            "label": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej: Terraza, Salón, Barra"}
            ),
        }

    def __init__(self, *args, restaurant: Restaurant | None = None, **kwargs):
        self.restaurant = restaurant
        super().__init__(*args, **kwargs)

    def clean_number(self):
        number = self.cleaned_data.get("number", "").strip()
        if not number:
            raise forms.ValidationError("El número o identificador de mesa es obligatorio.")
        if self.restaurant:
            qs = Table.objects.filter(restaurant=self.restaurant, number=number)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Ya existe una mesa con el número '{number}' en este restaurante.")
        return number


class MenuCategoryForm(forms.ModelForm):
    class Meta:
        model = MenuCategory
        fields = ["name", "display_order"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej: Entradas, Bebidas, Postres"}
            ),
            "display_order": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
        }


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = [
            "category",
            "name",
            "description",
            "weight_or_volume",
            "price",
            "image_url",
            "is_available",
            "display_order",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nombre del platillo o bebida"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 2, "placeholder": "Ingredientes, preparación..."}
            ),
            "weight_or_volume": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ej: 250 g, 350 ml"}
            ),
            "price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.50", "min": "0.01"}
            ),
            "image_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://..."}
            ),
            "is_available": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "display_order": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
        }

    def __init__(self, *args, restaurant: Restaurant | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if restaurant is not None:
            self.fields["category"].queryset = restaurant.categories.filter(is_active=True).order_by("display_order", "name")
        self.fields["is_available"].initial = True


class OpenOrderForm(forms.Form):
    waiter_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre del mesero (opcional)"}
        ),
    )
    guests_count = forms.IntegerField(
        min_value=1,
        max_value=50,
        initial=2,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 1, "max": 50}
        ),
    )
