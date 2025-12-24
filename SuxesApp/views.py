from django.shortcuts import render
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .forms import RegisterForm, CheckoutForm, AddressForm, EmailSubscriptionForm
from .utils import send_tiktok_server_event
from django.contrib import messages
from .models import (
    Cart, CartItem, Product, Category, Transaction, Size, 
    Color, UpcomingMerch, EmailSubscriber
)
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
import uuid
import requests
import random
import string
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse

# Create your views here.
def home(request):
    products = Product.objects.filter(is_active=True).order_by('name')
    categories = Category.objects.all()
    context = {
        'products': products,
        'categories': categories,
    }
    return render(request, 'SuxesApp/index.html', context)

def shop(request):
    # Get search query
    search_query = request.GET.get('search', '')

    # Base queryset
    products = Product.objects.filter(is_active=True)

    # Debug: Print queryset count
    print(f"Active products before filtering: {products.count()}")

    # Apply search filter
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(category__name__icontains=search_query)
        ).distinct()
        print(f"Products after search filter ({search_query}): {products.count()}")

    # Order products
    products = products.order_by('name')

    # Pagination
    paginator = Paginator(products, 6)  # 6 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'products': page_obj,
        'search_query': search_query,
        'cart_count': cart_item_count(request)['cart_count'],
    }
    return render(request, 'SuxesApp/shop.html', context)


@login_required(login_url='/login_user')
def checkout(request):
    categories = Category.objects.all()
    cart = None
    cart_items = []
    subtotal = 0
    total_price = 0
    address = None
    applied_discount = None
    discount_amount = 0

    try:
        cart = Cart.objects.get(user=request.user)
        cart_items = cart.items.all()
        subtotal = sum(item.total_price() for item in cart_items)
        
        # Check for applied discount code in session
        if request.session.get('discount_code'):
            try:
                from decimal import Decimal
                subscriber = EmailSubscriber.objects.get(
                    discount_code=request.session['discount_code'],
                    code_used=False,
                    is_active=True
                )
                stored_cart_total = Decimal(str(request.session.get('cart_total', '0')))
                
                # Verify the cart total hasn't changed significantly
                if abs(stored_cart_total - subtotal) < Decimal('1'):  # Allow for minor rounding differences
                    if subtotal >= 150000:
                        stored_discount = request.session.get('discount_amount', '0')
                        discount_amount = Decimal(str(stored_discount))
                        applied_discount = subscriber
                        total_price = subtotal - discount_amount
                    else:
                        # Clear discount if cart total drops below threshold
                        request.session.pop('discount_code', None)
                        request.session.pop('cart_total', None)
                        request.session.pop('discount_amount', None)
                        total_price = subtotal
                else:
                    # Cart total has changed significantly, clear discount
                    request.session.pop('discount_code', None)
                    request.session.pop('cart_total', None)
                    request.session.pop('discount_amount', None)
                    total_price = subtotal
            except EmailSubscriber.DoesNotExist:
                # Clear invalid discount code
                request.session.pop('discount_code', None)
                request.session.pop('cart_total', None)
                request.session.pop('discount_amount', None)
                total_price = subtotal
        else:
            total_price = subtotal
            
        address = request.user.address if hasattr(request.user, 'address') and request.user.address else None
    except Cart.DoesNotExist:
        messages.error(request, "Your cart is empty.")
        return redirect('cart')

    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect('cart')

    if request.method == 'POST':
        form = CheckoutForm(request.POST, instance=address)
        if form.is_valid():
            address = form.save()
            if not request.user.address:
                request.user.address = address
                request.user.save()
            messages.success(request, "Delivery address updated successfully.")
            # Create a transaction before redirecting to Flutterwave
            tx_ref = f"txn-{uuid.uuid4().hex[:10]}"  # Generate unique transaction reference
            transaction = Transaction.objects.create(
                user=request.user,
                amount=total_price,
                tx_ref=tx_ref,
                address=address,
                transaction_status='pending'
            )
            # Add products to the transaction
            transaction.products.set([item.product for item in cart_items])
            transaction.save()
            # Redirect to Flutterwave payment (handled in template)
            return redirect('initiate_payment', transaction_id=transaction.id)
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = CheckoutForm(instance=address)

    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'total_price': total_price,
        'form': form,
        'categories': categories,
        'applied_discount': applied_discount,
        'discount_amount': discount_amount,
    }
    return render(request, 'SuxesApp/checkout.html', context)

@login_required(login_url='/login_user')
def initiate_payment(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    cart = Cart.objects.get(user=request.user)
    cart_items = cart.items.all()

    context = {
        'transaction': transaction,
        'cart_items': cart_items,
        'public_key': settings.FLUTTERWAVE_PUBLIC_KEY,
        'redirect_url': 'https://www.suxesluxthread.com/payment-callback',
        'customer': {
            'name': f"{request.user.first_name} {request.user.last_name}",
            'email': request.user.email,
        },
    }
    return render(request, 'SuxesApp/initiate_payment.html', context)

import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# views.py
@csrf_exempt
@require_http_methods(["GET", "POST"])
def payment_callback(request):
    if request.method == "POST":
        try:
            webhook_data = json.loads(request.body.decode('utf-8'))
            event_type = webhook_data.get('event')
            transaction_data = webhook_data.get('data', {})
            tx_ref = transaction_data.get('tx_ref')
            transaction_id = transaction_data.get('id')
            status = transaction_data.get('status')

            try:
                transaction = Transaction.objects.get(tx_ref=tx_ref)
            except Transaction.DoesNotExist:
                return HttpResponse(status=404)

            if event_type == 'charge.completed' and status in ['successful', 'completed']:
                verification_response = verify_transaction(transaction_id)
                if (verification_response['status'] == 'success' and 
                    verification_response['data']['status'] in ['successful', 'completed'] and
                    verification_response['data']['amount'] == float(transaction.amount) and
                    verification_response['data']['currency'] == 'NGN'):
                    transaction.flw_transaction_id = transaction_id
                    transaction.transaction_status = 'processing'
                    transaction.save()
                    cart = Cart.objects.get(user=transaction.user)
                    cart_items = cart.items.all()
                    for cart_item in cart_items:
                        product = cart_item.product
                        if product.in_stock >= cart_item.quantity:
                            product.in_stock -= cart_item.quantity
                            product.save()
                        else:
                            transaction.transaction_status = 'declined'
                            transaction.save()
                            return HttpResponse(status=400)
                    cart_items.delete()
            elif status == 'failed':
                transaction.transaction_status = 'declined'
                transaction.save()
            return HttpResponse(status=200)
        except Exception as e:
            print(f"Webhook error: {str(e)}")
            return HttpResponse(status=400)

    elif request.method == "GET":
        status = request.GET.get('status')
        tx_ref = request.GET.get('tx_ref')
        transaction_id = request.GET.get('transaction_id')

        if status in ['successful', 'completed']:
            try:
                transaction = Transaction.objects.get(tx_ref=tx_ref)
                verification_response = verify_transaction(transaction_id)
                if (verification_response['status'] == 'success' and 
                    verification_response['data']['status'] in ['successful', 'completed'] and
                    verification_response['data']['amount'] == float(transaction.amount) and
                    verification_response['data']['currency'] == 'NGN'):
                    transaction.flw_transaction_id = transaction_id
                    transaction.transaction_status = 'processing'
                    transaction.save()
                    cart = Cart.objects.get(user=transaction.user)
                    cart_items = cart.items.all()
                    
                    # Prepare TikTok Event Data
                    tiktok_contents = []
                    
                    for cart_item in cart_items:
                        tiktok_contents.append({
                            'content_id': str(cart_item.product.id),
                            'content_name': cart_item.product.name,
                            'quantity': cart_item.quantity,
                            'price': float(cart_item.product.price)
                        })

                        product = cart_item.product
                        if product.in_stock >= cart_item.quantity:
                            product.in_stock -= cart_item.quantity
                            product.save()
                        else:
                            transaction.transaction_status = 'declined'
                            transaction.save()
                            messages.error(request, f"Insufficient stock for {product.name}.")
                            return redirect('cart')

                    # Send TikTok Server-Side Event: CompletePayment
                    try:
                        send_tiktok_server_event(
                            event_name='CompletePayment',
                            event_data={
                                'value': float(transaction.amount),
                                'currency': 'NGN',
                                'contents': tiktok_contents,
                                'content_type': 'product'
                            },
                            user=request.user,
                            event_id=str(transaction.id),
                            url=request.build_absolute_uri()
                        )
                    except Exception as e:
                        print(f"TikTok Event Error: {e}")

                    cart_items.delete()
                    messages.success(request, "Payment successful! Your order is being processed.")
                    return redirect('thank_you', transaction_id=transaction.id)  # Redirect to thank_you page
                else:
                    print(f"Verification failed: {verification_response}")
                    transaction.transaction_status = 'declined'
                    transaction.save()
                    messages.error(request, "Payment verification failed.")
            except Transaction.DoesNotExist:
                messages.error(request, "Transaction not found.")
        elif status == 'cancelled':
            try:
                transaction = Transaction.objects.get(tx_ref=tx_ref)
                transaction.transaction_status = 'declined'
                transaction.save()
                messages.error(request, "Payment was cancelled.")
            except Transaction.DoesNotExist:
                messages.error(request, "Transaction not found.")
        else:
            messages.error(request, f"Payment failed with status: {status}. Please try again.")

        return redirect('cart')

def thank_you(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)
    categories = Category.objects.all()
    cart_count = Cart.objects.get(user=request.user).items.count() if request.user.is_authenticated else 0

    context = {
        'transaction': transaction,
        'categories': categories,
        'cart_count': cart_count,
    }
    return render(request, 'SuxesApp/thank_you.html', context)



def verify_transaction(transaction_id):
    url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
    headers = {
        'Authorization': f'Bearer {settings.FLUTTERWAVE_SECRET_KEY}',
        'Content-Type': 'application/json',
    }
    response = requests.get(url, headers=headers)
    return response.json()


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    quantity = int(request.POST.get('quantity', 1))
    size_name = request.POST.get('size')
    color_name = request.POST.get('color')

    # If user is authenticated, fetch or create cart
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key, user=None)

    # Get size and color objects if provided
    size = None
    color = None
    if size_name:
        size = get_object_or_404(Size, name=size_name)
        if size not in product.sizes.all():
            messages.error(request, f"Selected size {size_name} is not available for {product.name}.")
            return redirect('product_detail', product_id=product.id)
    if color_name:
        color = get_object_or_404(Color, name=color_name)
        if color not in product.colors.all():
            messages.error(request, f"Selected color {color_name} is not available for {product.name}.")
            return redirect('product_detail', product_id=product.id)

    # Add or update cart item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        size=size,
        color=color
    )
    if not created:
        cart_item.quantity += quantity
    else:
        cart_item.quantity = quantity
    cart_item.save()

    # Set session variable for TikTok Pixel AddToCart event
    request.session['tiktok_pixel_add_to_cart'] = {
        'content_id': str(product.id),
        'content_name': product.name,
        'content_category': product.category.name if product.category else '',
        'quantity': quantity,
        'price': float(product.price),
        'value': float(product.price) * quantity,
        'currency': 'NGN',
    }

    messages.success(request, f"{product.name} ({size_name or 'No size'}, {color_name or 'No color'}) added to cart!")
    return redirect('product_detail', product_id=product.id)

def cart_item_count(request):
    count = 0
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)
        else:
            session_key = request.session.session_key
            if session_key:
                cart = Cart.objects.get(session_key=session_key)
            else:
                cart = None
        if cart:
            count = sum(item.quantity for item in cart.items.all())
    except Cart.DoesNotExist:
        pass
    return {'cart_count': count}

@require_POST
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id)
    cart_item.delete()
    messages.success(request, f"{cart_item.product.name} removed from cart!")
    return redirect('cart')


@login_required(login_url='/login_user')
def order_detail(request, transaction_id):
    # Fetch the transaction for the authenticated user
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)

    # Fetch cart items for the user (assuming cart was used for transaction)
    try:
        cart = Cart.objects.get(user=request.user)
        cart_items = cart.items.filter(product__in=transaction.products.all())
    except Cart.DoesNotExist:
        cart_items = []

    # Calculate cart count
    cart_count = cart.items.count() if Cart.objects.filter(user=request.user).exists() else 0

    context = {
        'transaction': transaction,
        'cart_items': cart_items,
        'cart_count': cart_count,
    }
    return render(request, 'SuxesApp/order_detail.html', context)

def profile(request):
    if not request.user.is_authenticated:
        return redirect('login_user')

    # Fetch user-related data
    user = request.user
    # Fetch user's transactions (order history)
    transactions = Transaction.objects.filter(user=user).order_by('-transaction_date')

    context = {
        'user': user,
        'address': user.address if hasattr(user, 'address') and user.address else None,
        'transactions': transactions,
        'cart_count': cart_item_count(request)['cart_count'],
    }
    return render(request, 'SuxesApp/profile.html', context)

@login_required(login_url='/login_user')
def edit_address(request):
    categories = Category.objects.all()
    user = request.user
    address = user.address if hasattr(user, 'address') and user.address else None

    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            address = form.save()
            if not user.address:
                user.address = address
                user.save()
            messages.success(request, "Address updated successfully.")
            return redirect('profile')
        else:
            messages.error(request, "Please correct the errors in the form.")
    else:
        form = AddressForm(instance=address)

    context = {
        'form': form,
        'is_edit': address,
        'categories': categories,
    }
    return render(request, 'SuxesApp/edit_address.html', context)

def cart(request):
    categories = Category.objects.all()
    cart = None
    cart_items = []
    total_price = 0
    subtotal = 0
    applied_discount = None
    discount_amount = 0

    try:
        # Get the cart
        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)
        else:
            session_key = request.session.session_key
            if session_key:
                cart = Cart.objects.get(session_key=session_key)
        
        if cart:
            cart_items = cart.items.all()
            subtotal = sum(item.total_price() for item in cart_items)
            
            # Handle discount code
            discount_code = request.session.get('discount_code')
            if discount_code and subtotal >= 150000:
                try:
                    subscriber = EmailSubscriber.objects.get(
                        discount_code=discount_code,
                        code_used=False,
                        is_active=True
                    )
                    # Use stored discount amount or calculate new one
                    from decimal import Decimal
                    stored_discount = request.session.get('discount_amount')
                    if stored_discount:
                        discount_amount = Decimal(stored_discount)
                    else:
                        discount_amount = subtotal * Decimal('0.10')
                    total_price = subtotal - discount_amount
                    applied_discount = subscriber
                except EmailSubscriber.DoesNotExist:
                    # Clear invalid discount
                    request.session.pop('discount_code', None)
                    request.session.pop('cart_total', None)
                    request.session.pop('discount_amount', None)
                    total_price = subtotal
            else:
                # Clear discount if total is below threshold
                if discount_code and subtotal < 150000:
                    messages.warning(request, 
                        'Your cart total is now below ₦150,000. '
                        'The discount code has been removed.'
                    )
                    request.session.pop('discount_code', None)
                    request.session.pop('cart_total', None)
                    request.session.pop('discount_amount', None)
                total_price = subtotal

    except Cart.DoesNotExist:
        pass

    # Fetch 4 random active products
    recommended_products = Product.objects.filter(is_active=True).order_by('?')[:4]

    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'total_price': total_price,
        'categories': categories,
        'recommended_products': recommended_products,
    }
    return render(request, 'SuxesApp/cart.html', context)

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    else:
        if request.method == 'POST':
            form = RegisterForm(request.POST)
            if form.is_valid():
                user = form.save(commit=False)
                user.save()  # Save the user before authenticating
                login(request, user)
                messages.success(request, f'Welcome, {user.username}! Your account has been created.')
                return redirect('home')
            else:
                messages.error(request, 'Error creating account. Please check the form.')
        else:
            form = RegisterForm()
    return render(request, 'SuxesApp/register.html', {'form': form})

def login_user(request):
    if request.user.is_authenticated:
        return redirect('home')
    else:
        error_message = None
        if request.method == 'POST':
            email = request.POST['email']
            password = request.POST['password']
            user = authenticate(request, email=email, password=password)

            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, 'Invalid email or password.')
        return render(request, 'SuxesApp/login.html', {'error_message': error_message})


def logout_user(request):
    logout(request)
    return redirect('home')

def product_detail(request, product_id):
    categories = Category.objects.all()
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    # Fetch related products in the same category (exclude current)
    category = product.category
    related_products = Product.objects.filter(
        category=category, is_active=True
    ).exclude(pk=product.pk)[:4]
    # Get available sizes and colors
    available_sizes = product.sizes.all()
    available_colors = product.colors.all()
    context = {
        'product': product,
        'related_products': related_products,
        'categories': categories,
        'available_sizes': available_sizes,
        'available_colors': available_colors,
    }
    return render(request, 'SuxesApp/product_detail.html', context)

def contact(request):
    categories = Category.objects.all()
    return render(request, 'SuxesApp/contact.html', {'categories': categories})

def about(request):
    categories = Category.objects.all()
    return render(request, 'SuxesApp/about.html', {'categories': categories})

def terms(request):
    categories = Category.objects.all()
    return render(request, 'SuxesApp/terms.html', {'categories': categories})

def privacy_policy(request):
    categories = Category.objects.all()
    return render(request, 'SuxesApp/privacy_policy.html', {'categories': categories})

def lookbook(request):
    categories = Category.objects.all()
    products = Product.objects.filter(is_active=True).order_by('-created_at')[:20]  # Show latest 20 products
    context = {
        'categories': categories,
        'products': products,
    }
    return render(request, 'SuxesApp/lookbook.html', context)

@require_POST
def get_discount_code(request):
    email = request.POST.get('email')
    if not email:
        return JsonResponse({'error': 'Email is required'}, status=400)

    # Generate random discount code
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

    # Save or update subscriber with discount code
    subscriber, created = EmailSubscriber.objects.get_or_create(email=email)
    if not created and subscriber.code_used:
        return JsonResponse({'error': 'Discount code already used'}, status=400)

    subscriber.discount_code = code
    subscriber.save()

    return JsonResponse({
        'success': True,
        'discount_code': code,
        'message': 'Your discount code has been sent! Use this code at checkout for 10% off orders above ₦150,000.'
    })

@require_POST
def apply_discount_code(request):
    """Apply discount code to the current cart."""
    try:
        # Get the discount code
        code = request.POST.get('discount_code', '').strip().upper()  # Convert to uppercase for consistency
        if not code:
            messages.error(request, 'Please enter a discount code.')
            return redirect('cart')

        # Get the cart
        cart = None
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
        else:
            session_key = request.session.session_key
            if session_key:
                cart = Cart.objects.filter(session_key=session_key).first()

        if not cart:
            messages.error(request, 'No active cart found.')
            return redirect('cart')

        if not cart.items.exists():
            messages.error(request, 'Your cart is empty.')
            return redirect('cart')

        # Calculate cart total first
        cart_total = sum(item.total_price() for item in cart.items.all())
        if cart_total < 150000:
            remaining = 150000 - cart_total
            messages.error(request, 
                f'Your order must be above ₦150,000 to use a discount code. '
                f'Add ₦{remaining:,.2f} more to qualify.'
            )
            return redirect('cart')

        # Check if code is already applied
        if request.session.get('discount_code') == code:
            messages.info(request, 'This discount code is already applied to your cart.')
            return redirect('cart')

        # Validate the discount code
        try:
            subscriber = EmailSubscriber.objects.get(
                discount_code=code,
                code_used=False,
                is_active=True
            )
        except EmailSubscriber.DoesNotExist:
            messages.error(request, 'Invalid or already used discount code.')
            return redirect('cart')

        # Calculate discount using Decimal for precise calculation
        from decimal import Decimal
        discount_percentage = Decimal('0.10')  # 10% as Decimal
        discount_amount = cart_total * discount_percentage
        new_total = cart_total - discount_amount

        # Clear any existing discount first
        request.session.pop('discount_code', None)
        request.session.pop('cart_total', None)
        request.session.pop('discount_amount', None)

        # Store new discount information in session
        request.session['discount_code'] = code
        request.session['cart_total'] = str(cart_total)  # Convert Decimal to string for session storage
        request.session['discount_amount'] = str(discount_amount)  # Convert Decimal to string for session storage
        request.session.modified = True

        # Mark the code as applied (but not used until checkout)
        messages.success(request, 
            f'Discount code applied successfully! '
            f'₦{discount_amount:,.2f} has been deducted from your total.'
        )
        return redirect('cart')

    except Cart.DoesNotExist:
        messages.error(request, 'No active cart found.')
        return redirect('cart')
    except ValueError as ve:
        messages.error(request, str(ve))
        return redirect('cart')
    except Exception as e:
        import traceback
        print(f"Error applying discount code: {str(e)}")
        print(traceback.format_exc())  # This will print the full error traceback
        messages.error(request, 'An unexpected error occurred. Please try again.')
        return redirect('cart')

def upcoming_merch(request):
    categories = Category.objects.all()
    upcoming_items = UpcomingMerch.objects.filter(is_active=True).order_by('release_date')
    
    if request.method == 'POST':
        form = EmailSubscriptionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Thank you for subscribing! You will be notified about new releases.')
            return redirect('upcoming_merch')
    else:
        form = EmailSubscriptionForm()

    context = {
        'categories': categories,
        'upcoming_items': upcoming_items,
        'form': form,
    }
    return render(request, 'SuxesApp/upcoming_merch.html', context)
