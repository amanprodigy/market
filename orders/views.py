import weasyprint

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.http import HttpResponseBadRequest

from .models import OrderItem, Order
from .forms import OrderCreateForm
from cart.cart import Cart
from .tasks import order_created


def order_create(request):
    cart = Cart(request)
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if cart.coupon:
                order.coupon = cart.coupon
                order.discount = cart.coupon.discount
                order.save()
            try:
                for item in cart:
                    OrderItem.objects.create(order=order,
                                             product=item['product'],
                                             price=item['price'],
                                             qty=item['qty'])
            except Exception as exp:
                return HttpResponseBadRequest(str(exp))

            # clear the cart
            cart.clear()
            # send email asynchronously
            order_created.delay(order.id)
            # set the order in the session
            request.session['order_id'] = order.id
            # redirect for payment
            return redirect(reverse('payment:process'))
    else:
        form = OrderCreateForm()
    return render(request,
                  'orders/order/create.html',
                  {'form': form, 'cart': cart})


@staff_member_required
def admin_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request,
                  'admin/orders/order/detail.html',
                  {'order': order})


@staff_member_required
def print_order_detail(request, order_id):
    """ function to demonstrate use of reportlab """
    from reportlab.pdfgen import canvas
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="orderprint.pdf"'

    # create pdf object using response object as its file
    p = canvas.Canvas(response)
    # Draw things on the pdf
    p.drawString(100, 100, "Hello World")
    # Close the pdf cleanly
    p.showPage()
    p.save()
    # order = get_object_or_404(Order, id=order_id)
    return response


@staff_member_required
def admin_order_pdf(request, order_id):
    """ print order details in pdf format """
    order = get_object_or_404(Order, id=order_id)
    html = render_to_string('orders/order/pdf.html',
                            {'order': order})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'filename="order_{}.pdf"\
        .format(order_id)'
    weasyprint.HTML(string=html).write_pdf(
        response,
        stylesheets=[weasyprint.CSS(
            settings.STATIC_ROOT + 'css/pdf.css'
        )])
    return response
