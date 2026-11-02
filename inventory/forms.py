from uuid import uuid4

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Complaint, ContactMessage, Item, Profile, StockRequest

User = get_user_model()


class RegistrationForm(UserCreationForm):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    department = forms.CharField(max_length=100)
    phone = forms.CharField(max_length=20, required=False, label="Contact No.")

    class Meta(UserCreationForm.Meta):
        fields = ["username", "first_name", "last_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class ProjectLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email ID",
        widget=forms.TextInput(
            attrs={"autocomplete": "username", "placeholder": "Organization email"}
        ),
    )


class NewRegistrationForm(RegistrationForm):
    role = forms.ChoiceField(choices=Profile.Role.choices, label="Post")

    field_order = [
        "first_name",
        "last_name",
        "department",
        "role",
        "email",
        "phone",
        "password1",
        "password2",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("username")
        self.fields["phone"].required = True
        self.fields["last_name"].required = False

    def save(self, commit=True):
        from uuid import uuid4

        user = super().save(commit=False)
        user.username = "lidms-" + uuid4().hex[:20]
        if commit:
            user.save()
        return user


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            "name",
            "asset_code",
            "category",
            "laboratory",
            "reorder_level",
            "description",
            "is_active",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class AdjustmentForm(forms.Form):
    delta = forms.IntegerField(
        min_value=-1000000,
        max_value=1000000,
        label="Units to add or remove",
        help_text="For example: 10 to receive stock, or -2 to remove damaged units.",
    )
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 3}))


def add_original_identity_fields(form, user, include_email=False):
    if user is None:
        return
    profile = getattr(user, "profile", None)
    values = {
        "first_name": ("First Name", user.first_name),
        "last_name": ("Last Name", user.last_name),
    }
    if include_email:
        values["email"] = ("Email ID", user.email)
    values.update(
        {
            "department": ("Department", profile.department if profile else ""),
            "post": ("Post", profile.get_role_display() if profile else "Faculty"),
        }
    )
    for key, (label, value) in values.items():
        form.fields[key] = forms.CharField(
            label=label, initial=value, required=False, disabled=True
        )
    form.order_fields(list(values) + [name for name in form.fields if name not in values])


class StockRequestForm(forms.ModelForm):
    quantity = forms.IntegerField(
        min_value=1, max_value=1000000, required=False, initial=1, widget=forms.HiddenInput
    )

    class Meta:
        model = StockRequest
        fields = ["equipment_needed", "purpose", "item", "quantity"]
        labels = {"equipment_needed": "Lab Equipment Needed", "purpose": "Description"}
        widgets = {"purpose": forms.Textarea(attrs={"rows": 4}), "item": forms.HiddenInput}

    def __init__(self, *args, user=None, selected_item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = Item.objects.filter(is_active=True)
        if selected_item:
            self.initial.update({"item": selected_item.pk, "equipment_needed": selected_item.name})
            self.fields["equipment_needed"].disabled = True
        if selected_item or self.data.get("item"):
            self.fields["quantity"].widget = forms.NumberInput(attrs={"min": 1})
            self.fields["quantity"].label = "Quantity needed"
        add_original_identity_fields(self, user, include_email=True)
        self.selected_item = selected_item

    def clean_quantity(self):
        return self.cleaned_data.get("quantity") or 1

    def clean(self):
        data = super().clean()
        if self.selected_item and data.get("item") != self.selected_item:
            self.add_error("item", "This request must use the selected equipment.")
        item = data.get("item")
        equipment = data.get("equipment_needed", "").strip()
        if item:
            data["equipment_needed"] = item.name
        elif not equipment:
            self.add_error("equipment_needed", "Enter the lab equipment you need.")
        return data


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(
        choices=[("approved", "Approve request"), ("rejected", "Reject request")]
    )
    note = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 3}))


class ReturnForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, label="Quantity returned")
    reason = forms.CharField(
        max_length=500, label="Condition / return note", widget=forms.Textarea(attrs={"rows": 3})
    )
    operation_id = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["subject", "priority", "complaint_type", "description", "laboratory", "item"]
        labels = {
            "subject": "Subject of Complaint",
            "priority": "Priority Level",
            "complaint_type": "Complaint Type",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "laboratory": forms.HiddenInput,
            "item": forms.HiddenInput,
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["item"].queryset = Item.objects.filter(is_active=True)
        self.fields["laboratory"].required = False
        self.fields["complaint_type"].required = False
        add_original_identity_fields(self, user)

    def clean_complaint_type(self):
        return self.cleaned_data.get("complaint_type") or "hardware"

    def clean_laboratory(self):
        return self.cleaned_data.get("laboratory") or "General laboratory"


class ComplaintUpdateForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ["assigned_to", "status", "resolution"]
        widgets = {"resolution": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, is_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True, profile__role=Profile.Role.TECHNICIAN
        )
        if not is_admin:
            self.fields.pop("assigned_to")

    def clean(self):
        data = super().clean()
        if (
            data.get("status") == Complaint.Status.RESOLVED
            and not data.get("resolution", "").strip()
        ):
            self.add_error(
                "resolution", "Describe the resolution before marking this complaint resolved."
            )
        return data


class UserAccessForm(forms.Form):
    role = forms.ChoiceField(choices=Profile.Role.choices)
    is_active = forms.BooleanField(required=False, label="Approved / active account")


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False, label="First name")
    last_name = forms.CharField(max_length=150, required=False, label="Last name")

    class Meta:
        model = Profile
        fields = ["department", "phone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.update(
            first_name=self.instance.user.first_name,
            last_name=self.instance.user.last_name,
        )
        self.order_fields(["first_name", "last_name", "department", "phone"])


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "message"]
        labels = {"name": "Name", "email": "Email ID", "message": "Message"}
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}
