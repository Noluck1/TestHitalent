from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Department, Employee
from .serializers import (
    ConflictError,
    DepartmentParentSerializer,
    DepartmentSerializer,
    DepartmentTreeSerializer,
    EmployeeSerializer,
    HiredAtSerializer,
    RequestBodySerializer,
    TextFieldSerializer,
    is_descendant,
    parse_bool,
)


MAX_DEPTH = 5


def error_response(message: str, status: int) -> JsonResponse:
    return JsonResponse({'error': message}, status=status)


class JsonRequestMixin:
    def parse_body(self, request: HttpRequest) -> dict:
        return RequestBodySerializer(request).parse()

    def validate_text(self, value: object, field_name: str) -> str:
        return TextFieldSerializer(value, field_name).validate()


class DepartmentsCollectionView(JsonRequestMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest) -> JsonResponse:
        try:
            data = self.parse_body(request)
            department = Department.objects.create(
                name=self.validate_text(data.get('name'), 'name'),
                parent=DepartmentParentSerializer(data.get('parent_id')).validate(),
            )
        except ValueError as exc:
            return error_response(str(exc), 400)
        except IntegrityError:
            return error_response(
                'Название подразделения должно быть уникальным внутри одного родителя',
                400,
            )
        return JsonResponse(DepartmentSerializer(department).data(), status=201)

    def http_method_not_allowed(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        return error_response('Метод не поддерживается', 405)


class DepartmentDetailView(JsonRequestMixin, View):
    http_method_names = ['get', 'patch', 'delete']

    def dispatch(
        self,
        request: HttpRequest,
        *args,
        **kwargs,
    ) -> JsonResponse | HttpResponse:
        self.department = get_object_or_404(
            Department.objects.select_related('parent'),
            id=kwargs['department_id'],
        )
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, department_id: int) -> JsonResponse:
        try:
            depth = int(request.GET.get('depth', '1'))
        except ValueError:
            return error_response('Параметр depth должен быть числом', 400)
        if depth < 0:
            return error_response(
                'Параметр depth должен быть больше или равен 0',
                400,
            )

        include_employees = parse_bool(request.GET.get('include_employees'), True)
        return JsonResponse(
            DepartmentTreeSerializer(
                self.department,
                min(depth, MAX_DEPTH),
                include_employees,
            ).data()
        )

    def patch(self, request: HttpRequest, department_id: int) -> JsonResponse:
        try:
            data = self.parse_body(request)
            if 'name' in data:
                self.department.name = self.validate_text(data['name'], 'name')
            if 'parent_id' in data:
                self.department.parent = DepartmentParentSerializer(
                    data['parent_id'],
                    self.department,
                ).validate()
            with transaction.atomic():
                self.department.save()
        except ConflictError as exc:
            return error_response(str(exc), 409)
        except ValueError as exc:
            return error_response(str(exc), 400)
        except IntegrityError:
            return error_response(
                'Название подразделения должно быть уникальным внутри одного родителя',
                400,
            )
        return JsonResponse(DepartmentSerializer(self.department).data())

    def delete(self, request: HttpRequest, department_id: int) -> HttpResponse | JsonResponse:
        mode = request.GET.get('mode', 'cascade')
        if mode == 'cascade':
            self.department.delete()
            return HttpResponse(status=204)
        if mode != 'reassign':
            return error_response('Параметр mode должен быть cascade или reassign', 400)

        try:
            reassign_to_id = int(request.GET['reassign_to_department_id'])
        except KeyError:
            return error_response(
                'Для режима reassign нужен параметр reassign_to_department_id',
                400,
            )
        except ValueError:
            return error_response(
                'Параметр reassign_to_department_id должен быть числом',
                400,
            )
        if reassign_to_id == self.department.id:
            return error_response(
                'Нельзя перенести сотрудников в удаляемое подразделение',
                400,
            )

        reassign_to = get_object_or_404(Department, id=reassign_to_id)
        if is_descendant(reassign_to, self.department):
            return error_response(
                'Нельзя перенести сотрудников в поддерево удаляемого подразделения',
                409,
            )

        with transaction.atomic():
            Employee.objects.filter(department=self.department).update(
                department=reassign_to
            )
            Department.objects.filter(parent=self.department).update(
                parent=self.department.parent
            )
            self.department.delete()
        return HttpResponse(status=204)

    def http_method_not_allowed(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        return error_response('Метод не поддерживается', 405)


class DepartmentEmployeesView(JsonRequestMixin, View):
    http_method_names = ['post']

    def post(self, request: HttpRequest, department_id: int) -> JsonResponse:
        department = get_object_or_404(Department, id=department_id)
        try:
            data = self.parse_body(request)
            employee = Employee.objects.create(
                department=department,
                full_name=self.validate_text(data.get('full_name'), 'full_name'),
                position=self.validate_text(data.get('position'), 'position'),
                hired_at=HiredAtSerializer(data.get('hired_at')).validate(),
            )
        except ValueError as exc:
            return error_response(str(exc), 400)
        return JsonResponse(EmployeeSerializer(employee).data(), status=201)

    def http_method_not_allowed(self, request: HttpRequest, *args, **kwargs) -> JsonResponse:
        return error_response('Метод не поддерживается', 405)


departments_collection = csrf_exempt(DepartmentsCollectionView.as_view())
department_detail = csrf_exempt(DepartmentDetailView.as_view())
department_employees = csrf_exempt(DepartmentEmployeesView.as_view())
