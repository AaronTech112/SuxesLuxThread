from .models import Cart

def cart_item_count(request):
    count = 0
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)
        else:
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
            session_key = request.session.session_key
            cart = Cart.objects.get(session_key=session_key)
        if cart:
            count = sum(item.quantity for item in cart.items.all())
    except Cart.DoesNotExist:
        pass
    return {'cart_count': count}
