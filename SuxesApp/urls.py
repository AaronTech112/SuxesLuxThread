from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


# Create your views here.
urlpatterns = [
    path('', views.home, name='home'),    
    path('register', views.register, name='register'),
    path('shop/', views.shop, name='shop'),
    path('login_user', views.login_user, name='login_user'),
    path('logout_user', views.logout_user, name='logout_user'),
    path('profile', views.profile, name='profile'),
    path('cart', views.cart, name='cart'),
    path('add_to_cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('product_detail/<int:product_id>/', views.product_detail, name='product_detail'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),  # Placeholder for checkout view
    path('edit-address/', views.edit_address, name='edit_address'),
    path('initiate-payment/<int:transaction_id>/', views.initiate_payment, name='initiate_payment'),
    path('payment-callback/', views.payment_callback, name='payment_callback'),
    path('order-detail/<int:transaction_id>/', views.order_detail, name='order_detail'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('lookbook/', views.lookbook, name='lookbook'),
    path('thank-you/<int:transaction_id>/', views.thank_you, name='thank_you'), 
]