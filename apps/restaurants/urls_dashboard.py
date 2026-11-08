from django.urls import path

from apps.restaurants import views_dashboard

urlpatterns = [
    path("login/", views_dashboard.dashboard_login, name="login"),
    path("register/", views_dashboard.dashboard_register, name="register"),
    path("logout/", views_dashboard.dashboard_logout, name="logout"),
    path("", views_dashboard.dashboard_home, name="dashboard_home"),
    path("<slug:slug>/", views_dashboard.restaurant_dashboard, name="restaurant_dashboard"),
    path(
        "<slug:slug>/settings/",
        views_dashboard.restaurant_settings,
        name="restaurant_settings",
    ),
    path(
        "<slug:slug>/tables/add/",
        views_dashboard.table_create,
        name="restaurant_table_add",
    ),
    path(
        "<slug:slug>/tables/<str:table_number>/delete/",
        views_dashboard.table_delete,
        name="restaurant_table_delete",
    ),
    path(
        "<slug:slug>/menu/",
        views_dashboard.menu_manage,
        name="restaurant_menu_manage",
    ),
    path(
        "<slug:slug>/menu/category/add/",
        views_dashboard.category_create,
        name="restaurant_category_add",
    ),
    path(
        "<slug:slug>/menu/item/add/",
        views_dashboard.menu_item_create,
        name="restaurant_menu_item_add",
    ),
    path(
        "<slug:slug>/menu/item/<int:item_id>/toggle/",
        views_dashboard.menu_item_toggle,
        name="restaurant_menu_item_toggle",
    ),
    path(
        "<slug:slug>/table/<str:table_number>/",
        views_dashboard.table_pos,
        name="restaurant_table_pos",
    ),
    path(
        "<slug:slug>/table/<str:table_number>/open/",
        views_dashboard.pos_open_order,
        name="pos_open_order",
    ),
    path(
        "<slug:slug>/table/<str:table_number>/add-item/",
        views_dashboard.pos_add_item,
        name="pos_add_item",
    ),
    path(
        "<slug:slug>/table/<str:table_number>/update-item/<int:item_id>/",
        views_dashboard.pos_update_item,
        name="pos_update_item",
    ),
    path(
        "<slug:slug>/table/<str:table_number>/close/",
        views_dashboard.pos_close_order,
        name="pos_close_order",
    ),
    path(
        "<slug:slug>/table/<str:table_number>/qr/",
        views_dashboard.table_qr_print,
        name="restaurant_table_qr",
    ),
]
