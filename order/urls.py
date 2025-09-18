from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'order'

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('add-item', views.add_item, name='add_item'),
    path('confirm-order', views.confirm_order, name='confirm_order'),
    path('order-summary', views.view_summary, name='order_summary'),
    path('delete-item/<int:product_id>/<int:size_id>', views.delete_item, name='delete-item'),
    path('product-create', views.product_create, name='product_create'),
    path('product-list', views.product_list, name='product_list'),
    path('product-update/<int:pk>', views.product_update, name='product_update'),
    path('product-delete/<int:pk>', views.product_delete, name='product_delete'),
    path('dashboard/', views.dashboard, name='dashboard'),
]