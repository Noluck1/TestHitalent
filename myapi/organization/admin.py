from django.contrib import admin

from .models import Department, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'parent', 'created_at')
    search_fields = ('name',)
    list_filter = ('parent',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'position', 'department', 'hired_at', 'created_at')
    search_fields = ('full_name', 'position')
    list_filter = ('department',)
