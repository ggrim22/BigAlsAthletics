from django.urls import path

from . import views

app_name = 'order'

urlpatterns = [
    path('', views.index, name='index'),
    path('add-item', views.add_item, name='add_item'),
    path('confirm-order', views.confirm_order, name='confirm_order'),
    path('order-summary', views.view_summary, name='order_summary'),
    path('delete-item/<int:product_id>/<int:size_id>', views.delete_item, name='delete-item'),
    path('product-create', views.product_create, name='product_create'),
    path('product-list', views.product_list, name='product_list'),
    path('product-update/<int:pk>', views.product_update, name='product_update'),
    path('product-delete/<int:pk>', views.product_delete, name='product_delete'),
    path('product-dashboard/', views.product_dashboard, name='product_dashboard'),
    path('order-dashboard/', views.order_dashboard, name='order_dashboard'),
    path('order-list', views.order_list, name='order_list'),
    path("orders/<int:order_id>/toggle_paid/", views.toggle_paid, name="toggle_paid"),
    path('summary', views.summary, name='summary'),
    path('collection-create', views.collection_create, name='collection_create'),
    path('collection-update/<int:pk>', views.collection_update, name='collection_update'),
    path('collection-delete/<int:pk>', views.collection_delete, name='collection_delete'),
    path('collection-dashboard/', views.collection_dashboard, name='collection_dashboard'),
    path('collection-list', views.collection_list, name='collection_list'),
    path('shopping-cart', views.shopping_cart, name='shopping_cart'),
]