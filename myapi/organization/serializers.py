import json
from datetime import date
from json import JSONDecodeError
from typing import Any

from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from .models import Department, Employee


class ConflictError(Exception):
    pass


class RequestBodySerializer:
    def __init__(self, request: HttpRequest) -> None:
        self.request = request

    def parse(self) -> dict[str, Any]:
        if not self.request.body:
            return {}
        try:
            data = json.loads(self.request.body)
        except JSONDecodeError as exc:
            raise ValueError('Тело запроса должно быть валидным JSON') from exc
        if not isinstance(data, dict):
            raise ValueError('Тело запроса должно быть JSON-объектом')
        return data


class TextFieldSerializer:
    max_length = 200

    def __init__(self, value: object, field_name: str) -> None:
        self.value = value
        self.field_name = field_name

    def validate(self) -> str:
        if not isinstance(self.value, str):
            raise ValueError(f'Поле {self.field_name} должно быть строкой')
        value = self.value.strip()
        if not value:
            raise ValueError(f'Поле {self.field_name} не должно быть пустым')
        if len(value) > self.max_length:
            raise ValueError(
                f'Поле {self.field_name} должно быть не длиннее {self.max_length} символов'
            )
        return value


class HiredAtSerializer:
    def __init__(self, value: object) -> None:
        self.value = value

    def validate(self) -> date | None:
        if self.value in (None, ''):
            return None
        if not isinstance(self.value, str):
            raise ValueError(
                'Дата найма должна быть строкой в формате ГГГГ-ММ-ДД или пустым значением'
            )
        try:
            return date.fromisoformat(self.value)
        except ValueError as exc:
            raise ValueError('Дата найма должна быть в формате ГГГГ-ММ-ДД') from exc


class DepartmentParentSerializer:
    def __init__(
        self,
        parent_id: object,
        department: Department | None = None,
    ) -> None:
        self.parent_id = parent_id
        self.department = department

    def validate(self) -> Department | None:
        if self.parent_id is None:
            return None
        if not isinstance(self.parent_id, int):
            raise ValueError(
                'ID родительского подразделения должен быть числом или null'
            )
        if self.department and self.parent_id == self.department.id:
            raise ValueError('Подразделение не может быть родителем самого себя')

        parent = get_object_or_404(
            Department.objects.select_related('parent'),
            id=self.parent_id,
        )
        if self.department and self._is_descendant(parent, self.department):
            raise ConflictError(
                'Нельзя переместить подразделение внутрь его собственного поддерева'
            )
        return parent

    @staticmethod
    def _is_descendant(candidate_parent: Department, department: Department) -> bool:
        current = candidate_parent
        while current.parent_id is not None:
            if current.parent_id == department.id:
                return True
            current = current.parent
        return False


class DepartmentSerializer:
    def __init__(self, department: Department) -> None:
        self.department = department

    def data(self) -> dict[str, Any]:
        return {
            'id': self.department.id,
            'name': self.department.name,
            'parent_id': self.department.parent_id,
            'created_at': self.department.created_at.isoformat(),
        }


class EmployeeSerializer:
    def __init__(self, employee: Employee) -> None:
        self.employee = employee

    def data(self) -> dict[str, Any]:
        return {
            'id': self.employee.id,
            'department_id': self.employee.department_id,
            'full_name': self.employee.full_name,
            'position': self.employee.position,
            'hired_at': self.employee.hired_at.isoformat()
            if self.employee.hired_at
            else None,
            'created_at': self.employee.created_at.isoformat(),
        }


class DepartmentTreeSerializer:
    def __init__(
        self,
        department: Department,
        depth: int,
        include_employees: bool,
    ) -> None:
        self.department = department
        self.depth = depth
        self.include_employees = include_employees

    def data(self) -> dict[str, Any]:
        return self._serialize(self.department, self.depth)

    def _serialize(self, department: Department, depth: int) -> dict[str, Any]:
        data = DepartmentSerializer(department).data()
        if self.include_employees:
            employees = department.employees.order_by('created_at', 'full_name')
            data['employees'] = [
                EmployeeSerializer(employee).data() for employee in employees
            ]

        data['children'] = []
        if depth > 0:
            children = department.children.order_by('name', 'id')
            data['children'] = [
                self._serialize(child, depth - 1) for child in children
            ]
        return data


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {'1', 'true', 'yes', 'on'}


def is_descendant(candidate_parent: Department, department: Department) -> bool:
    return DepartmentParentSerializer._is_descendant(candidate_parent, department)
