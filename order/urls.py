from django.urls import path

from . import views

app_name = 'order'

urlpatterns = [
    path('', views.index, name='index'),
    path('add-item', views.add_item, name='add_item'),
    path('confirm-order', views.confirm_order, name='confirm_order'),
    path('order-summary', views.view_summary, name='order_summary'),
    path('delete-item/<int:product_id>/<str:size>', views.delete_item, name='delete-item'),
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
    path("shopping-cart/", views.shopping_cart, name="shopping_cart"),
    path('order-download', views.order_download, name='order_download'),
    path('order-summary-download', views.order_summary_download, name='order_summary_download'),
    path('product-category-create', views.product_category_create, name='product_category_create'),
    path('product-color-create', views.product_color_create, name='product_color_create'),
    path('product/<int:product_id>/add-variant/', views.add_or_update_variant, name='add_product_variant'),
    path('product/<int:product_id>/sizes/', views.get_variant_sizes, name='get_variant_sizes'),
    path('product/<int:product_id>/price/', views.get_variant_price, name='get_variant_price'),
    path('collection/<int:collection_id>', views.products, name='products'),
    path("payment-success/", views.payment_success, name="payment-success"),
    path("payment-cancel/", views.payment_cancel, name="payment-cancel"),
    path("about", views.about, name='about'),
    path('bulk-delete/', views.bulk_delete_orders, name='bulk_delete_orders'),
    path('bulk-archive/', views.bulk_archive_orders, name='bulk_archive_orders'),
    path('archived/', views.archived_orders, name='archived_orders'),
    path('restore/<int:order_id>/', views.restore_order, name='restore_order'),
    path('contact-page', views.contact_page, name='contact'),

]