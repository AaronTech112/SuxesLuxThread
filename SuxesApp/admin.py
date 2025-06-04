from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import (
    CustomUser,
    Address,
    Category,
    Product,
    Transaction,
    Cart,
    CartItem,
    Color,
    Size,
    ProductImage,
)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('tx_ref', 'user', 'amount', 'transaction_status', 'transaction_date', 'flw_transaction_id')
    list_filter = ('transaction_status', 'transaction_date')
    search_fields = ('tx_ref', 'user__username', 'user__email', 'flw_transaction_id')
    list_editable = ('transaction_status',)  # Allow inline status changes
    readonly_fields = ('transaction_date', 'flw_transaction_id', 'tx_ref', 'amount', 'user', 'products')
    filter_horizontal = ('products',)  # Better UI for ManyToMany field

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'is_staff',
    )
    list_filter = (
        'is_staff', 'is_active',
    )
    search_fields = (
        'email', 'username', 'first_name', 'last_name',
    )
    ordering = ('email',)
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {'fields': (
            'phone_number', 'profile_picture', 'bio', 'address',
        )}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': (
            'phone_number', 'profile_picture', 'bio', 'address',
        )}),
    )

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('street', 'city', 'state', 'postal_code', 'country')
    search_fields = ('street', 'city', 'state', 'postal_code', 'country')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name', 'description')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'session_key')
    search_fields = ('user__username', 'session_key')

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity')
    search_fields = ('product__name',)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'in_stock', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description')
    inlines = [ProductImageInline]
    filter_horizontal = ('sizes', 'colors')  # Use filter_horizontal for better many-to-many UI
    
@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('name', 'hex_code')
    search_fields = ('name',)