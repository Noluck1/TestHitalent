import json

from django.test import Client, TestCase

from .models import Department, Employee


class OrganizationApiTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def post_json(self, path: str, data: dict):
        return self.client.post(
            path,
            data=json.dumps(data),
            content_type='application/json',
        )

    def patch_json(self, path: str, data: dict):
        return self.client.patch(
            path,
            data=json.dumps(data),
            content_type='application/json',
        )

    def test_create_department_and_employee(self) -> None:
        department_response = self.post_json('/departments/', {'name': ' Backend '})

        self.assertEqual(department_response.status_code, 201)
        department_id = department_response.json()['id']
        self.assertEqual(department_response.json()['name'], 'Backend')

        employee_response = self.post_json(
            f'/departments/{department_id}/employees/',
            {
                'full_name': 'Ivan Petrov',
                'position': 'Developer',
                'hired_at': '2026-05-28',
            },
        )

        self.assertEqual(employee_response.status_code, 201)
        self.assertEqual(employee_response.json()['department_id'], department_id)
        self.assertEqual(Employee.objects.count(), 1)

    def test_get_department_tree_respects_depth(self) -> None:
        root = Department.objects.create(name='Root')
        child = Department.objects.create(name='Child', parent=root)
        Department.objects.create(name='Grandchild', parent=child)

        response = self.client.get(f'/departments/{root.id}?depth=1')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['name'], 'Root')
        self.assertEqual(len(data['children']), 1)
        self.assertEqual(data['children'][0]['children'], [])

    def test_move_department_inside_own_subtree_is_conflict(self) -> None:
        root = Department.objects.create(name='Root')
        child = Department.objects.create(name='Child', parent=root)

        response = self.patch_json(f'/departments/{root.id}', {'parent_id': child.id})

        self.assertEqual(response.status_code, 409)

    def test_delete_department_reassigns_employees_and_children(self) -> None:
        root = Department.objects.create(name='Root')
        target = Department.objects.create(name='Target')
        child = Department.objects.create(name='Child', parent=root)
        employee = Employee.objects.create(
            department=root,
            full_name='Ivan Petrov',
            position='Developer',
        )

        response = self.client.delete(
            f'/departments/{root.id}?mode=reassign&reassign_to_department_id={target.id}'
        )

        self.assertEqual(response.status_code, 204)
        employee.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(employee.department_id, target.id)
        self.assertIsNone(child.parent_id)
        self.assertFalse(Department.objects.filter(id=root.id).exists())
