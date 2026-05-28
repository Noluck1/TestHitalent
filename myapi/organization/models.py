from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=200, blank=False)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'name'],
                name='unique_department_name_per_parent',
                nulls_distinct=False,
            )
        ]

    def __str__(self):
        return self.name


class Employee(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='employees',
    )
    full_name = models.CharField(max_length=200, blank=False)
    position = models.CharField(max_length=200, blank=False)
    hired_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name
