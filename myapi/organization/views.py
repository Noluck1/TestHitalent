import json
from datetime import date
from json import JSONDecodeError

from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import Department, Employee


MAX_DEPTH = 5


def error_response(message: str, status: int) -> JsonResponse:
    return JsonResponse({'error': message}, status=status)


def parse_json_body(request: HttpRequest) -> dict:
    if not request.body:
        return {}
    try:
        data = json.loads(request.body)
    except JSONDecodeError as exc:
        raise ValueError('Тело запроса должно быть валидным JSON') from exc
    if not isinstance(data, dict):
        raise ValueError('Тело запроса должно быть JSON-объектом')
    return data


def parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {'1', 'true', 'yes', 'on'}


def validate_text(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f'Поле {field_name} должно быть строкой')
    value = value.strip()
    if not value:
        raise ValueError(f'Поле {field_name} не должно быть пустым')
    if len(value) > 200:
        raise ValueError(f'Поле {field_name} должно быть не длиннее 200 символов')
    return value


def parse_hired_at(value: object) -> date | None:
    if value in (None, ''):
        return None
    if not isinstance(value, str):
        raise ValueError('Дата найма должна быть строкой в формате ГГГГ-ММ-ДД или пустым значением')
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('Дата найма должна быть в формате ГГГГ-ММ-ДД') from exc


def serialize_department(department: Department) -> dict:
    return {
        'id': department.id,
        'name': department.name,
        'parent_id': department.parent_id,
        'created_at': department.created_at.isoformat(),
    }


def serialize_employee(employee: Employee) -> dict:
    return {
        'id': employee.id,
        'department_id': employee.department_id,
        'full_name': employee.full_name,
        'position': employee.position,
        'hired_at': employee.hired_at.isoformat() if employee.hired_at else None,
        'created_at': employee.created_at.isoformat(),
    }


def serialize_department_tree(
    department: Department,
    depth: int,
    include_employees: bool,
) -> dict:
    data = serialize_department(department)
    if include_employees:
        employees = department.employees.order_by('created_at', 'full_name')
        data['employees'] = [serialize_employee(employee) for employee in employees]
    data['children'] = []
    if depth > 0:
        children = department.children.order_by('name', 'id')
        data['children'] = [
            serialize_department_tree(child, depth - 1, include_employees)
            for child in children
        ]
    return data


def is_descendant(candidate_parent: Department, department: Department) -> bool:
    current = candidate_parent
    while current.parent_id is not None:
        if current.parent_id == department.id:
            return True
        current = current.parent
    return False


def parse_parent(parent_id: object, department: Department | None = None) -> Department | None:
    if parent_id is None:
        return None
    if not isinstance(parent_id, int):
        raise ValueError('ID родительского подразделения должен быть числом или null')
    if department and parent_id == department.id:
        raise ValueError('Подразделение не может быть родителем самого себя')
    parent = get_object_or_404(Department.objects.select_related('parent'), id=parent_id)
    if department and is_descendant(parent, department):
        raise ConflictError('Нельзя переместить подразделение внутрь его собственного поддерева')
    return parent


class ConflictError(Exception):
    pass


@csrf_exempt
def departments_collection(request: HttpRequest) -> JsonResponse:
    if request.method != 'POST':
        return error_response('Метод не поддерживается', 405)
    try:
        data = parse_json_body(request)
        name = validate_text(data.get('name'), 'name')
        parent = parse_parent(data.get('parent_id'))
        department = Department.objects.create(name=name, parent=parent)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except IntegrityError:
        return error_response('Название подразделения должно быть уникальным внутри одного родителя', 400)
    return JsonResponse(serialize_department(department), status=201)


@csrf_exempt
def department_detail(request: HttpRequest, department_id: int) -> JsonResponse | HttpResponse:
    department = get_object_or_404(Department.objects.select_related('parent'), id=department_id)
    if request.method == 'GET':
        return get_department(request, department)
    if request.method == 'PATCH':
        return update_department(request, department)
    if request.method == 'DELETE':
        return delete_department(request, department)
    return error_response('Метод не поддерживается', 405)


@csrf_exempt
def department_employees(request: HttpRequest, department_id: int) -> JsonResponse:
    if request.method != 'POST':
        return error_response('Метод не поддерживается', 405)
    department = get_object_or_404(Department, id=department_id)
    try:
        data = parse_json_body(request)
        employee = Employee.objects.create(
            department=department,
            full_name=validate_text(data.get('full_name'), 'full_name'),
            position=validate_text(data.get('position'), 'position'),
            hired_at=parse_hired_at(data.get('hired_at')),
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    return JsonResponse(serialize_employee(employee), status=201)


def get_department(request: HttpRequest, department: Department) -> JsonResponse:
    try:
        depth = int(request.GET.get('depth', '1'))
    except ValueError:
        return error_response('Параметр depth должен быть числом', 400)
    if depth < 0:
        return error_response('Параметр depth должен быть больше или равен 0', 400)
    depth = min(depth, MAX_DEPTH)
    include_employees = parse_bool(request.GET.get('include_employees'), True)
    return JsonResponse(serialize_department_tree(department, depth, include_employees))


def update_department(request: HttpRequest, department: Department) -> JsonResponse:
    try:
        data = parse_json_body(request)
        if 'name' in data:
            department.name = validate_text(data['name'], 'name')
        if 'parent_id' in data:
            department.parent = parse_parent(data['parent_id'], department)
        with transaction.atomic():
            department.save()
    except ConflictError as exc:
        return error_response(str(exc), 409)
    except ValueError as exc:
        return error_response(str(exc), 400)
    except IntegrityError:
        return error_response('Название подразделения должно быть уникальным внутри одного родителя', 400)
    return JsonResponse(serialize_department(department))


def delete_department(request: HttpRequest, department: Department) -> HttpResponse | JsonResponse:
    mode = request.GET.get('mode', 'cascade')
    if mode == 'cascade':
        department.delete()
        return HttpResponse(status=204)
    if mode != 'reassign':
        return error_response('Параметр mode должен быть cascade или reassign', 400)
    try:
        reassign_to_id = int(request.GET['reassign_to_department_id'])
    except KeyError:
        return error_response('Для режима reassign нужен параметр reassign_to_department_id', 400)
    except ValueError:
        return error_response('Параметр reassign_to_department_id должен быть числом', 400)
    if reassign_to_id == department.id:
        return error_response('Нельзя перенести сотрудников в удаляемое подразделение', 400)
    reassign_to = get_object_or_404(Department, id=reassign_to_id)
    if is_descendant(reassign_to, department):
        return error_response('Нельзя перенести сотрудников в поддерево удаляемого подразделения', 409)
    with transaction.atomic():
        Employee.objects.filter(department=department).update(department=reassign_to)
        Department.objects.filter(parent=department).update(parent=department.parent)
        department.delete()
    return HttpResponse(status=204)
