"""
filters.py

This page is used to register filter for employee models

"""
import uuid
from django import forms
import django_filters
from django.contrib.auth.models import Permission, Group
from django import forms
from django_filters.filters import ModelChoiceFilter
from django.utils.translation import gettext as _
from base.methods import reload_queryset
from base.models import WorkType
from horilla.filters import FilterSet
from employee.models import Employee


class EmployeeFilter(FilterSet):
    """
    Filter set class for Candidate model

    Args:
        FilterSet (class): custom filter set class to apply styling
    """

    search = django_filters.CharFilter(method="filter_by_name")

    employee_first_name = django_filters.CharFilter(lookup_expr="icontains")
    employee_last_name = django_filters.CharFilter(lookup_expr="icontains")
    country = django_filters.CharFilter(lookup_expr="icontains")
    department = django_filters.CharFilter(
        field_name="employee_work_info__department_id__department",
        lookup_expr="icontains",
    )
    # gender = django_filters.ChoiceFilter(field_name="gender",lookup_expr="iexact")

    user_permissions = django_filters.ModelMultipleChoiceFilter(
        queryset=Permission.objects.all(),
    )
    groups = django_filters.ModelMultipleChoiceFilter(
        queryset=Group.objects.all(),
    )
    is_active = django_filters.ChoiceFilter(
        field_name="is_active",
        label="Is Active",
        choices=[
            (True, "Yes"),
            (False, "No"),
        ],
    )

    not_in_yet = django_filters.DateFilter(
        method="not_in_yet_func",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    not_out_yet = django_filters.DateFilter(
        method="not_out_yet_func",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    class Meta:
        """
        Meta class to add the additional info
        """

        model = Employee
        fields = [
            "employee_first_name",
            "employee_last_name",
            "email",
            "badge_id",
            "phone",
            "country",
            "gender",
            "is_active",
            "employee_work_info__job_position_id",
            "employee_work_info__department_id",
            "department",
            "employee_work_info__work_type_id",
            "employee_work_info__employee_type_id",
            "employee_work_info__job_role_id",
            "employee_work_info__reporting_manager_id",
            "employee_work_info__company_id",
            "employee_work_info__shift_id",
            "employee_work_info__tags"
        ]

    def not_in_yet_func(self, queryset, _, value):
        """
        The method to filter out the not check-in yet employees
        """

        # Getting the queryset for those employees dont have any attendance for the date
        # in value.
        queryset = queryset.exclude(
            employee_attendances__attendance_date=value,
        )
        return queryset

    def not_out_yet_func(self, queryset, _, value):
        """
        The method to filter out the not check-in yet employees
        """

        # Getting the queryset for those employees dont have any attendance for the date
        # in value.
        queryset = queryset.filter(
            employee_attendances__attendance_date=value,
            employee_attendances__attendance_clock_out__isnull=True,
        )
        return queryset

    def filter_queryset(self, queryset):
        """
        Override the default filtering behavior to handle None option.
        """
        data = self.form.cleaned_data
        not_set_dict = {key: value for key, value in data.items() if value == "not_set"}
        if not_set_dict:
            filtered_data = queryset
            for key, value in not_set_dict.items():
                not_set = f"{key}__isnull"
                filtered_data = filtered_data.filter(**{not_set: True})
            return filtered_data
        return super().filter_queryset(queryset)

        # Continue with the default behavior for other filters

    def filter_by_name(self, queryset, _, value):
        """
        Filter queryset by first name or last name.
        """
        # Split the search value into first name and last name
        parts = value.split()
        first_name = parts[0]
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        # Filter the queryset by first name and last name
        if first_name and last_name:
            queryset = queryset.filter(
                employee_first_name__icontains=first_name,
                employee_last_name__icontains=last_name,
            )
        elif first_name:
            queryset = queryset.filter(employee_first_name__icontains=first_name)
        elif last_name:
            queryset = queryset.filter(employee_last_name__icontains=last_name)
        return queryset

    def __init__(self, data=None, queryset=None, *, request=None, prefix=None):
        super().__init__(data=data, queryset=queryset, request=request, prefix=prefix)
        self.form.fields["is_active"].initial = True
        for field in self.form.fields.keys():
            self.form.fields[field].widget.attrs["id"] = f"{uuid.uuid4()}"
        self.model_choice_filters = [
            filter
            for filter in self.filters.values()
            if isinstance(filter, django_filters.ModelChoiceFilter)
        ]
        for model_choice_filter in self.model_choice_filters:
            queryset = (
                model_choice_filter.queryset.filter(is_active=True)
                if model_choice_filter.queryset.model == Employee
                else model_choice_filter.queryset
            )
            choices = [
                ("", "---------"),
                ("not_set", _("Not Set")),
            ]
            choices.extend([(obj.id, str(obj)) for obj in queryset])
            self.form.fields[model_choice_filter.field_name] = forms.ChoiceField(
                choices=choices,
                required=False,
                widget=forms.Select(
                    attrs={
                        "class": "oh-select oh-select-2 select2-hidden-accessible",
                        "id": uuid.uuid4(),
                    }
                ),
            )


class EmployeeReGroup:
    """
    Class to keep the field name for group by option
    """

    fields = [
        ("", "select"),
        ("employee_work_info.job_position_id", "Job Position"),
        ("employee_work_info.department_id", "Department"),
        ("employee_work_info.shift_id", "Shift"),
        ("employee_work_info.work_type_id", "Work Type"),
        ("employee_work_info.job_role_id", "Job Role"),
        ("employee_work_info.reporting_manager_id", "Reporting Manager"),
        ("employee_work_info.company_id", "Company"),
    ]
