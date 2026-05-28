from django.urls import path

from . import views

urlpatterns = [
    path('departments/', views.departments_collection, name='departments_collection'),
    path('departments/<int:department_id>', views.department_detail, name='department_detail'),
    path(
        'departments/<int:department_id>/employees/',
        views.department_employees,
        name='department_employees',
    ),
]
