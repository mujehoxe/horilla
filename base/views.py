"""
views.py

This module is used to map url pattens with django views or methods
"""

from django import forms
from django.apps import apps
from datetime import timedelta, datetime
from urllib.parse import parse_qs, urlencode
import uuid
import json
from django.db.models import ProtectedError
from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.utils.translation import gettext as _
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import Group, User, Permission
from attendance.forms import AttendanceValidationConditionForm
from attendance.models import AttendanceValidationCondition, GraceTime
from django.views.decorators.csrf import csrf_exempt
from employee.filters import EmployeeFilter
from employee.forms import ActiontypeForm
from horilla_audit.forms import HistoryTrackingFieldsForm
from horilla_audit.models import AuditTag, HistoryTrackingFields
from notifications.models import Notification
from notifications.base.models import AbstractNotification
from notifications.signals import notify
from horilla.decorators import (
    delete_permission,
    permission_required,
    login_required,
    manager_can_enter,
)
from horilla.settings import EMAIL_HOST_USER
from employee.models import Actiontype, Employee, EmployeeTag, EmployeeWorkInformation
from base.decorators import (
    shift_request_change_permission,
    work_type_request_change_permission,
)
from base.methods import closest_numbers, export_data, get_pagination
from base.forms import (
    AnnouncementExpireForm,
    AuditTagForm,
    CompanyForm,
    DepartmentForm,
    DynamicMailConfForm,
    DynamicPaginationForm,
    EmployeeTagForm,
    JobPositionForm,
    JobRoleForm,
    EmployeeShiftForm,
    EmployeeShiftScheduleForm,
    EmployeeTypeForm,
    RotatingShiftAssignExportForm,
    RotatingWorkTypeAssignExportForm,
    ShiftAllocationForm,
    ShiftRequestColumnForm,
    ShiftrequestcommentForm,
    WorkTypeForm,
    UserGroupForm,
    RotatingShiftForm,
    RotatingShiftAssign,
    RotatingWorkTypeForm,
    RotatingWorkTypeAssignForm,
    RotatingShiftAssignForm,
    ShiftRequestForm,
    WorkTypeRequestColumnForm,
    WorkTypeRequestForm,
    RotatingShiftAssignUpdateForm,
    RotatingWorkTypeAssignUpdateForm,
    EmployeeShiftScheduleUpdateForm,
    AssignUserGroup,
    AssignPermission,
    ResetPasswordForm,
    ChangePasswordForm,
    TagsForm,
    MultipleApproveConditionForm,
    WorktyperequestcommentForm,
)
from base.models import (
    Announcement,
    AnnouncementExpire,
    AnnouncementView,
    BaserequestFile,
    Company,
    DynamicEmailConfiguration,
    DynamicPagination,
    JobPosition,
    JobRole,
    Department,
    MultipleApprovalCondition,
    MultipleApprovalManagers,
    ShiftrequestComment,
    WorkType,
    EmployeeShift,
    EmployeeShiftDay,
    EmployeeShiftSchedule,
    EmployeeType,
    RotatingWorkType,
    RotatingWorkTypeAssign,
    RotatingShift,
    ShiftRequest,
    WorkTypeRequest,
    Tags,
    WorktyperequestComment,
)
from base.filters import (
    RotatingShiftRequestReGroup,
    RotatingWorkTypeRequestReGroup,
    ShiftRequestFilter,
    ShiftRequestReGroup,
    WorkTypeRequestFilter,
    RotatingShiftAssignFilters,
    RotatingWorkTypeAssignFilter,
    WorkTypeRequestReGroup,
)
from base.methods import (
    choosesubordinates,
    filtersubordinates,
    get_key_instances,
    sortby,
)
from payroll.forms.forms import EncashmentGeneralSettingsForm
from payroll.forms.component_forms import PayrollSettingsForm
from payroll.models.models import EncashmentGeneralSettings
from payroll.models.tax_models import PayrollSettings
from helpdesk.models import TicketType
from helpdesk.forms import TicketTypeForm


def custom404(request):
    """
    Custom 404 method
    """
    return render(request, "404.html")


# Create your views here.
def is_reportingmanger(request, instance):
    """
    If the instance have employee id field then you can use this method to know the request
    user employee is the reporting manager of the instance
    """
    manager = request.user.employee_get
    try:
        employee_work_info_manager = (
            instance.employee_id.employee_work_info.reporting_manager_id
        )
    except Exception:
        return HttpResponse("This Employee Dont Have any work information")
    return manager == employee_work_info_manager


def paginator_qry(queryset, page_number):
    """
    Common paginator method
    """
    paginator = Paginator(queryset, get_pagination())
    queryset = paginator.get_page(page_number)
    return queryset


def login_user(request):
    """
    This method is used render login template and authenticate user
    """

    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        next_url = request.GET.get("next")
        query_params = request.GET.dict()
        if "next" in query_params:
            del query_params["next"]

        params = f"{urlencode(query_params)}"

        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, _("Invalid username or password."))
            return redirect("/login")
        if user.employee_get.is_active == False:
            messages.error(
                request,
                _(
                    "This user is archived. Please contact the manager for more information."
                ),
            )
            return redirect("/login")
        login(request, user)
        messages.success(request, _("Login Success"))
        if next_url:
            url = f"{next_url}"
            if params:
                url += f"?{params}"
            return redirect(url)
        return redirect("/")
    return render(request, "login.html")


def include_employee_instance(request, form):
    """
    This method is used to include the employee instance to the form
    Args:
        form: django forms instance
    """
    queryset = form.fields["employee_id"].queryset
    employee = Employee.objects.filter(employee_user_id=request.user)
    if employee.first() is not None:
        if queryset.filter(id=employee.first().id).first() is None:
            queryset = queryset | employee
            form.fields["employee_id"].queryset = queryset
    return form


reset_ids = []


def forgot_password(request):
    """
    This method is used to send the reset password link to the employee email
    """
    if request.method == "POST":
        id = str(uuid.uuid4())
        username = request.POST["email"]
        user = User.objects.filter(username=username).first()
        if user is not None:
            employee = Employee.objects.filter(employee_user_id=user).first()
            if employee is not None:
                if employee.email is not None:
                    send_link(employee, request, id, user)
                else:
                    messages.error(request, _("No email found."))
        else:
            messages.error(request, "User not found")
    return render(request, "forgot_password.html")


def send_link(employee, request, id, user):
    """
    Here actually the link will send to the employee email
    """
    recipient = [
        employee.email,
    ]
    subject = "Link To Rest Your Password!"
    url = request.build_absolute_uri("/") + "reset-password/" + id
    message = f"Reset Your Password {url}."
    reset_ids.append({"uuid": id, "user": user})
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=EMAIL_HOST_USER,
            recipient_list=recipient,
        )
        response_success = _("Link sended to {recipient}").format(recipient=recipient)
        messages.success(request, response_success)
    except Exception as e:
        messages.error(request, e)


def reset_password(request, uuid):
    """
    This method is used to reset the current password for the employee
    """
    user = next((item["user"] for item in reset_ids if item["uuid"] == uuid), None)
    form = ResetPasswordForm()
    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            form.save(user=user)
            messages.success(request, _("Password reset success"))
            reset_ids.remove({"uuid": uuid, "user": user})
            return redirect("/login")
    if user is None:
        return HttpResponse(_("Link Expired..."))
    return render(request, "reset_password.html", {"form": form})


@login_required
def change_password(request):
    user = request.user
    form = ChangePasswordForm(user=user)
    if request.method == "POST":
        response = render(request, "base/auth/password_change.html", {"form": form})
        form = ChangePasswordForm(user, request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]
            user.set_password(new_password)
            user.save()
            user = authenticate(request, username=user.username, password=new_password)
            login(request, user)
            messages.success(request, _("Password changed successfully"))
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(request, "base/auth/password_change.html", {"form": form})


def logout_user(request):
    """
    This method used to logout the user
    """
    if request.user:
        logout(request)
    response = HttpResponse()
    response.content = """
        <script>
            localStorage.clear();
        </script>
        <meta http-equiv="refresh" content="0;url=/login">
    """

    return response


class Workinfo:
    def __init__(self, employee) -> None:
        self.employee_work_info = employee
        self.employee_id = employee
        self.id = employee.id
        pass


@login_required
def home(request):
    """
    This method is used to render index page
    """
    if len(EmployeeShiftDay.objects.all()) == 0:
        days = (
            ("monday", "Monday"),
            ("tuesday", "Tuesday"),
            ("wednesday", "Wednesday"),
            ("thursday", "Thursday"),
            ("friday", "Friday"),
            ("saturday", "Saturday"),
            ("sunday", "Sunday"),
        )
        for day in days:
            shift_day = EmployeeShiftDay()
            shift_day.day = day[0]
            shift_day.save()

    today = datetime.today()
    today_weekday = today.weekday()
    first_day_of_week = today - timedelta(days=today_weekday)
    last_day_of_week = first_day_of_week + timedelta(days=6)

    employees_with_pending = []

    # List of field names to focus on
    fields_to_focus = [
        "job_position_id",
        "department_id",
        "work_type_id",
        "employee_type_id",
        "job_role_id",
        "reporting_manager_id",
        "company_id",
        "location",
        "email",
        "mobile",
        "shift_id",
        "date_joining",
        "contract_end_date",
        "basic_salary",
        "salary_hour",
    ]

    for employee in EmployeeWorkInformation.objects.filter(employee_id__is_active=True):
        completed_field_count = sum(
            1
            for field_name in fields_to_focus
            if getattr(employee, field_name) is not None
        )
        if completed_field_count < 14:
            # Create a dictionary with employee information and pending field count
            percent = f"{((completed_field_count / 14) * 100):.1f}"
            employee_info = {
                "employee": employee,
                "completed_field_count": percent,
            }
            employees_with_pending.append(employee_info)
        else:
            pass

    emps = Employee.objects.filter(employee_work_info__isnull=True)
    for emp in emps:
        employees_with_pending.insert(
            0,
            {
                "employee": Workinfo(employee=emp),
                "completed_field_count": "0",
            },
        )
    announcements = Announcement.objects.all().order_by('-created_on')
    announcement_list = announcements.filter(employees=request.user.employee_get)
    announcement_list =announcement_list | announcements.filter(employees__isnull=True)
    if request.user.has_perm("base.view_announcement"):
        announcement_list = announcements
    general_expire = AnnouncementExpire.objects.all().first()
    general_expire_date = 30 if not general_expire else general_expire.days

    for announcement in announcement_list:
        if announcement.expire_date is None:
            calculated_expire_date = announcement.created_on + timedelta(
                days=general_expire_date
            )
            announcement.expire_date = calculated_expire_date

        # Check if the user has viewed the announcement
        announcement_view = AnnouncementView.objects.filter(
            announcement=announcement, user=request.user
        ).first()
        announcement.has_viewed = (
            announcement_view is not None and announcement_view.viewed
        )

    context = {
        "first_day_of_week": first_day_of_week.strftime("%Y-%m-%d"),
        "last_day_of_week": last_day_of_week.strftime("%Y-%m-%d"),
        "employees_with_pending": employees_with_pending,
        "announcement": announcement_list,
        "general_expire_date": general_expire_date,
    }

    return render(request, "index.html", context)


@login_required
def common_settings(request):
    """
    This method is used to render setting page template
    """
    return render(request, "settings.html")


@login_required
@permission_required("auth.add_group")
def user_group_table(request):
    """
    Group assign htmx view
    """
    permissions = []
    apps = [
        "base",
        "recruitment",
        "employee",
        "leave",
        "pms",
        "onboarding",
        "asset",
        "attendance",
        "payroll",
        "auth",
        "offboarding",
        "horilla_documents",
        "helpdesk",
    ]
    form = UserGroupForm()
    for app_name in apps:
        app_models = []
        for model in get_models_in_app(app_name):
            app_models.append(
                {
                    "verbose_name": model._meta.verbose_name.capitalize(),
                    "model_name": model._meta.model_name,
                }
            )
        permissions.append({"app": app_name.capitalize(), "app_models": app_models})
    if request.method == "POST":
        form = UserGroupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("User group created."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/auth/group_assign.html",
        {
            "permissions": permissions,
            "form": form,
        },
    )


@login_required
@require_http_methods(["POST"])
@permission_required("auth.add_permission")
def update_group_permission(
    request,
):
    """
    This method is used to remove user permission.
    """
    group_id = request.POST["id"]
    instance = Group.objects.get(id=group_id)
    form = UserGroupForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({"message": "Updated the permissions", "type": "success"})
    if request.POST.get("name_update"):
        name = request.POST["name"]
        if len(name) > 3:
            instance.name = name
            instance.save()
            return JsonResponse({"message": "Name updated", "type": "success"})
        return JsonResponse(
            {"message": "At least 4 characters required", "type": "success"}
        )
    perms = form.cleaned_data.get("permissions")
    if not perms:
        instance.permissions.clear()
        return JsonResponse({"message": "All permission cleared", "type": "info"})
    return JsonResponse({"message": "Something went wrong", "type": "danger"})


@login_required
@permission_required("auth.view_group")
def user_group(request):
    """
    This method is used to create user permission group
    """
    permissions = []

    apps = [
        "base",
        "recruitment",
        "employee",
        "leave",
        "pms",
        "onboarding",
        "asset",
        "attendance",
        "payroll",
        "auth",
        "offboarding",
        "horilla_documents",
        "helpdesk",
    ]
    form = UserGroupForm()
    for app_name in apps:
        app_models = []
        for model in get_models_in_app(app_name):
            app_models.append(
                {
                    "verbose_name": model._meta.verbose_name.capitalize(),
                    "model_name": model._meta.model_name,
                }
            )
        permissions.append({"app": app_name.capitalize(), "app_models": app_models})
    groups = Group.objects.all()
    return render(
        request,
        "base/auth/group.html",
        {
            "permissions": permissions,
            "form": form,
            "groups": paginator_qry(groups, request.GET.get("page")),
        },
    )


@login_required
@permission_required("auth.view_group")
def user_group_search(request):
    """
    This method is used to create user permission group
    """
    permissions = []

    apps = [
        "base",
        "recruitment",
        "employee",
        "leave",
        "pms",
        "onboarding",
        "asset",
        "attendance",
        "payroll",
        "auth",
        "offboarding",
        "horilla_documents",
        "helpdesk",
    ]
    form = UserGroupForm()
    for app_name in apps:
        app_models = []
        for model in get_models_in_app(app_name):
            app_models.append(
                {
                    "verbose_name": model._meta.verbose_name.capitalize(),
                    "model_name": model._meta.model_name,
                }
            )
        permissions.append({"app": app_name.capitalize(), "app_models": app_models})
    search = ""
    if request.GET.get("search"):
        search = str(request.GET["search"])
    groups = Group.objects.filter(name__icontains=search)
    return render(
        request,
        "base/auth/group_lines.html",
        {
            "permissions": permissions,
            "form": form,
            "groups": paginator_qry(groups, request.GET.get("page")),
        },
    )


@login_required
@permission_required("auth.add_group")
def group_assign(request):
    """
    This method is used to assign user group to the users.
    """
    group_id = request.GET["group"]
    form = AssignUserGroup(
        initial={
            "group": group_id,
            "employee": Employee.objects.filter(
                employee_user_id__groups__id=group_id
            ).values_list("id", flat=True),
        }
    )
    if request.POST:
        group_id = request.POST["group"]
        form = AssignUserGroup(
            {"group": group_id, "employee": request.POST.getlist("employee")}
        )
        if form.is_valid():
            form.save()
            messages.success(request, _("User group assigned."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/auth/group_user_assign.html",
        {"form": form, "group_id": group_id},
    )


@login_required
@permission_required("auth.view_group")
def group_assign_view(request):
    """
    This method is used to search the user groups
    """
    search = ""
    if request.GET.get("search") is not None:
        search = request.GET.get("search")
    groups = Group.objects.filter(name__icontains=search)
    previous_data = request.GET.urlencode()
    return render(
        request,
        "base/auth/group_assign_view.html",
        {"groups": paginator_qry(groups, request.GET.get("page")), "pd": previous_data},
    )


@login_required
@permission_required("auth.view_group")
def user_group_view(request):
    """
    This method is used to render template for view all groups
    """
    search = ""
    if request.GET.get("search") is not None:
        search = request.GET["search"]
    user_group = Group.objects.filter()
    return render(request, "base/auth/group_assign.html", {"data": user_group})


@login_required
@permission_required("change_group")
@require_http_methods(["POST"])
def user_group_permission_remove(request, pid, gid):
    """
    This method is used to remove permission from group.
    args:
        pid: permission id
        gid: group id
    """
    group = Group.objects.get(id=1)
    permission = Permission.objects.get(id=2)
    group.permissions.remove(permission)
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@permission_required("change_group")
@require_http_methods(["POST"])
def group_remove_user(request, uid, gid):
    """
    This method is used to remove an user from group permission.
    args:
        uid: user instance id
        gid: group instance id
    """
    group = Group.objects.get(id=gid)
    user = User.objects.get(id=uid)
    group.user_set.remove(user)
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@permission_required("change_group")
def user_group_update(request, id, **kwargs):
    """
    This method is used to render updating form template for user permission group
    args:
        id : group instance id
    """
    group = Group.objects.get(id=id)
    form = UserGroupForm(instance=group)
    if request.method == "POST":
        form = UserGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, _("User group updated."))
            return redirect(user_group_create)

    groups = Group.objects.all()
    return render(request, "base/auth/group.html", {"form": form, "groups": groups})


@login_required
@delete_permission()
@require_http_methods(["POST", "DELETE"])
def object_delete(request, id, **kwargs):
    model = kwargs["model"]
    redirect_path = kwargs["redirect"]
    try:
        instance = model.objects.get(id=id)
        instance.delete()
        messages.success(
            request, _("The {} has been deleted successfully.").format(instance)
        )
    except model.DoesNotExist:
        messages.error(request, _("{} not found.").format(model._meta.verbose_name))
    except ProtectedError as e:
        model_verbose_names_set = set()
        for obj in e.protected_objects:
            model_verbose_names_set.add(_(obj._meta.verbose_name.capitalize()))

        model_names_str = ", ".join(model_verbose_names_set)
        messages.error(
            request,
            _("This {} is already in use for {}.").format(instance, model_names_str),
        ),
    return redirect(redirect_path)


@login_required
@delete_permission()
def object_duplicate(request, obj_id, **kwargs):
    model = kwargs["model"]
    form_class = kwargs["form"]
    template = kwargs["template"]
    original_object = model.objects.get(id=obj_id)
    form = form_class(instance=original_object)
    if request.method == "GET":
        for field_name, field in form.fields.items():
            if isinstance(field, forms.CharField):
                initial_value = f"{form.initial.get(field_name, '')} (copy)"
                form.initial[field_name] = initial_value
                form.fields[field_name].initial = initial_value
        if hasattr(form.instance, "id"):
            form.instance.id = None

    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            new_object = form.save(commit=False)
            new_object.id = None
            new_object.save()
            return HttpResponse("<script>window.location.reload()</script>")

    context = {
        kwargs.get("form_name", "form"): form,
        "obj_id": obj_id,
        "duplicate": True,
    }
    return render(request, template, context)


@login_required
@permission_required("base.view_dynamicemailconfiguration")
def mail_server_conf(request):
    mail_servers = DynamicEmailConfiguration.objects.all()
    return render(
        request, "base/mail_server/mail_server.html", {"mail_servers": mail_servers}
    )


@login_required
@permission_required("base.delete_dynamicemailconfiguration")
def mail_server_delete(request):
    ids = request.GET.getlist("ids")
    DynamicEmailConfiguration.objects.filter(id__in=ids).delete()
    messages.success(request, "Mail server configuration deleted")
    return redirect(mail_server_conf)


@login_required
@permission_required("base.add_dynamicemailconfiguration")
def mail_server_create_or_update(request):
    instance_id = request.GET.get("instance_id")
    instance = None
    if instance_id:
        instance = DynamicEmailConfiguration.objects.filter(id=instance_id).first()
    form = DynamicMailConfForm(instance=instance)
    if request.method == "POST":
        form = DynamicMailConfForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request, "base/mail_server/form.html", {"form": form, "instance": instance}
    )


@login_required
@permission_required("base.add_company")
def company_create(request):
    """
    This method render template and form to create company and save if the form is valid
    """

    form = CompanyForm()
    companies = Company.objects.all()
    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()

            messages.success(request, _("Company has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")

    return render(
        request,
        "base/company/company_form.html",
        {"form": form, "companies": companies},
    )


@login_required
@permission_required("base.view_company")
def company_view(request):
    """
    This method used to view created companies
    """

    companies = Company.objects.all()
    return render(request, "base/company/company.html", {"companies": companies})


@login_required
@permission_required("base.change_company")
def company_update(request, id, **kwargs):
    """
    This method is used to update company
    args:
        id : company instance id

    """
    company = Company.objects.get(id=id)
    form = CompanyForm(instance=company)
    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, _("Company updated"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request, "base/company/company_form.html", {"form": form, "company": company}
    )


@login_required
@permission_required("base.add_department")
def department_create(request):
    """
    This method renders form and template to create department
    """

    form = DepartmentForm()
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            form = DepartmentForm()
            messages.success(request, _("Department has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/department/department_form.html",
        {
            "form": form,
        },
    )


@login_required
def department_view(request):
    """
    This method view department
    """
    departments = Department.objects.all()
    return render(
        request,
        "base/department/department.html",
        {
            "departments": departments,
        },
    )


@login_required
@permission_required("base.change_department")
def department_update(request, id, **kwargs):
    """
    This method is used to update department
    args:
        id : department instance id
    """
    department = Department.objects.get(id=id)
    form = DepartmentForm(instance=department)
    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, _("Department updated."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/department/department_form.html",
        {"form": form, "department": department},
    )


@login_required
@permission_required("base.view_jobposition")
def job_position(request):
    """
    This method is used to view job position
    """

    departments = Department.objects.all()
    jobs = False
    if JobPosition.objects.exists():
        jobs = True
    form = JobPositionForm()
    if request.method == "POST":
        form = JobPositionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Job Position has been created successfully!"))
    return render(
        request,
        "base/job_position/job_position.html",
        {"form": form, "departments": departments, "jobs": jobs},
    )


@login_required
@permission_required("base.add_jobposition")
def job_position_creation(request):
    """
    This method is used to create job position
    """
    dynamic = request.GET.get("dynamic")
    form = JobPositionForm()
    if request.method == "POST":
        form = JobPositionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Job Position has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/job_position/job_position_form.html",
        {
            "form": form,
            "dynamic": dynamic,
        },
    )


@login_required
@permission_required("base.change_jobposition")
def job_position_update(request, id, **kwargs):
    """
    This method is used to update job position
    args:
        id : job position instance id

    """
    job_position = JobPosition.objects.get(id=id)
    form = JobPositionForm(instance=job_position)
    if request.method == "POST":
        form = JobPositionForm(request.POST, instance=job_position)
        if form.is_valid():
            form.save()
            messages.success(request, _("Job position updated."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/job_position/job_position_form.html",
        {"form": form, "job_position": job_position},
    )


@login_required
@permission_required("base.add_jobrole")
def job_role_create(request):
    """
    This method is used to create job role.
    """
    dynamic = request.GET.get("dynamic")
    form = JobRoleForm()
    if request.method == "POST":
        form = JobRoleForm(request.POST)
        if form.is_valid():
            form.save()
            form = JobRoleForm()

            messages.success(request, _("Job role has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")

    return render(
        request,
        "base/job_role/job_role_form.html",
        {
            "form": form,
            "dynamic": dynamic,
        },
    )


@login_required
@permission_required("base.view_jobrole")
def job_role_view(request):
    """
    This method is used to view job role.
    """

    jobs = JobPosition.objects.all()
    job_role = False
    if JobRole.objects.exists():
        job_role = True

    return render(
        request,
        "base/job_role/job_role.html",
        {"job_positions": jobs, "job_role": job_role},
    )


@login_required
@permission_required("base.change_jobrole")
def job_role_update(request, id, **kwargs):
    """
    This method is used to update job role instance
    args:
        id  : job role instance id

    """

    job_role = JobRole.objects.get(id=id)

    form = JobRoleForm(instance=job_role)
    if request.method == "POST":
        form = JobRoleForm(request.POST, instance=job_role)
        if form.is_valid():
            form.save()
            messages.success(request, _("Job role updated."))
            return HttpResponse("<script>window.location.reload()</script>")

    return render(
        request,
        "base/job_role/job_role_form.html",
        {
            "form": form,
            "job_role": job_role,
        },
    )


@login_required
@permission_required("base.add_worktype")
def work_type_create(request):
    """
    This method is used to create work type
    """
    dynamic = request.GET.get("dynamic")
    form = WorkTypeForm()
    work_types = WorkType.objects.all()
    if request.method == "POST":
        form = WorkTypeForm(request.POST)
        if form.is_valid():
            form.save()
            form = WorkTypeForm()

            messages.success(request, _("Work Type has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")

    return render(
        request,
        "base/work_type/work_type_form.html",
        {"form": form, "work_types": work_types, "dynamic": dynamic},
    )


@login_required
@permission_required("base.view_worktype")
def work_type_view(request):
    """
    This method is used to view work type
    """

    work_types = WorkType.objects.all()
    return render(
        request,
        "base/work_type/work_type.html",
        {"work_types": work_types},
    )


@login_required
@permission_required("base.change_worktype")
def work_type_update(request, id, **kwargs):
    """
    This method is used to update work type instance
    args:
        id : work type instance id

    """

    work_type = WorkType.objects.get(id=id)
    form = WorkTypeForm(instance=work_type)
    if request.method == "POST":
        form = WorkTypeForm(request.POST, instance=work_type)
        if form.is_valid():
            form.save()
            messages.success(request, _("Work type updated."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/work_type/work_type_form.html",
        {"form": form, "work_type": work_type},
    )


@login_required
@permission_required("base.add_rotatingworktype")
def rotating_work_type_create(request):
    """
    This method is used to create rotating work type   .
    """

    form = RotatingWorkTypeForm()
    if request.method == "POST":
        form = RotatingWorkTypeForm(request.POST)
        if form.is_valid():
            form.save()
            form = RotatingWorkTypeForm()

            messages.success(request, _("Rotating work type created."))
            return HttpResponse("<script>window.location.reload()</script>")

            return redirect(rotating_work_type_create)
    return render(
        request,
        "base/rotating_work_type/htmx/rotating_work_type_form.html",
        {"form": form, "rwork_type": RotatingWorkType.objects.all()},
    )


@login_required
@permission_required("base.view_rotatingworktype")
def rotating_work_type_view(request):
    """
    This method is used to view rotating work type   .
    """

    return render(
        request,
        "base/rotating_work_type/rotating_work_type.html",
        {"rwork_type": RotatingWorkType.objects.all()},
    )


@login_required
@permission_required("base.change_rotatingworktype")
def rotating_work_type_update(request, id, **kwargs):
    """
    This method is used to update rotating work type instance.
    args:
        id : rotating work type instance id

    """

    rotating_work_type = RotatingWorkType.objects.get(id=id)
    form = RotatingWorkTypeForm(instance=rotating_work_type)
    if request.method == "POST":
        form = RotatingWorkTypeForm(request.POST, instance=rotating_work_type)
        if form.is_valid():
            form.save()
            messages.success(request, _("Rotating work type updated."))
            return HttpResponse("<script>window.location.reload()</script>")

    return render(
        request,
        "base/rotating_work_type/htmx/rotating_work_type_form.html",
        {"form": form, "r_type": rotating_work_type},
    )


@login_required
@manager_can_enter("base.view_rotatingworktypeassign")
def rotating_work_type_assign(request):
    """
    This method is used to assign rotating work type to employee users
    """

    filter = RotatingWorkTypeAssignFilter(
        queryset=RotatingWorkTypeAssign.objects.filter(is_active=True)
    )
    rwork_all = RotatingWorkTypeAssign.objects.all()
    rwork_type_assign = filter.qs
    rwork_type_assign = filtersubordinates(
        request, rwork_type_assign, "base.view_rotatingworktypeassign"
    )
    rwork_type_assign = rwork_type_assign.filter(employee_id__is_active=True)
    assign_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                rwork_type_assign, request.GET.get("page")
            ).object_list
        ]
    )
    return render(
        request,
        "base/rotating_work_type/rotating_work_type_assign.html",
        {
            "f": filter,
            "export_filter": RotatingWorkTypeAssignFilter(),
            "export_columns": RotatingWorkTypeAssignExportForm(),
            "rwork_type_assign": paginator_qry(
                rwork_type_assign, request.GET.get("page")
            ),
            "assign_ids": assign_ids,
            "rwork_all": rwork_all,
            "gp_fields": RotatingWorkTypeRequestReGroup.fields,
        },
    )


@login_required
@manager_can_enter("base.add_rotatingworktypeassign")
def rotating_work_type_assign_add(request):
    """
    This method is used to assign rotating work type
    """
    form = RotatingWorkTypeAssignForm()
    if request.GET.get("emp_id"):
        employee = request.GET.get("emp_id")
        form = RotatingWorkTypeAssignForm(initial={"employee_id": employee})
    form = choosesubordinates(request, form, "base.add_rotatingworktypeassign")
    if request.method == "POST":
        form = RotatingWorkTypeAssignForm(request.POST)
        form = choosesubordinates(request, form, "base.add_rotatingworktypeassign")
        if form.is_valid():
            form.save()
            employee_ids = request.POST.getlist("employee_id")
            employees = Employee.objects.filter(id__in=employee_ids).select_related(
                "employee_user_id"
            )
            users = [employee.employee_user_id for employee in employees]
            notify.send(
                request.user.employee_get,
                recipient=users,
                verb="You are added to rotating work type",
                verb_ar="تمت إضافتك إلى نوع العمل المتناوب",
                verb_de="Sie werden zum rotierenden Arbeitstyp hinzugefügt",
                verb_es="Se le agrega al tipo de trabajo rotativo",
                verb_fr="Vous êtes ajouté au type de travail rotatif",
                icon="infinite",
                redirect="/employee/employee-profile/",
            )

            messages.success(request, _("Rotating work type assigned."))
            response = render(
                request,
                "base/rotating_work_type/htmx/rotating_work_type_assign_form.html",
                {"form": form},
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(
        request,
        "base/rotating_work_type/htmx/rotating_work_type_assign_form.html",
        {"form": form},
    )


@login_required
@manager_can_enter("base.view_rotatingworktypeassign")
def rotating_work_type_assign_view(request):
    """
    This method renders template to view rotating work type objects
    """

    previous_data = request.GET.urlencode()
    rwork_type_assign = RotatingWorkTypeAssignFilter(request.GET).qs
    field = request.GET.get("field")
    rwork_type_assign = rwork_type_assign.filter(is_active=True)
    if request.GET.get("is_active") == "false":
        rwork_type_assign = rwork_type_assign.filter(is_active=False)
    rwork_type_assign = filtersubordinates(
        request, rwork_type_assign, "base.view_rotatingworktypeassign"
    )
    template = "base/rotating_work_type/rotating_work_type_assign_view.html"
    data_dict = parse_qs(previous_data)
    get_key_instances(RotatingWorkTypeAssign, data_dict)
    if field != "" and field is not None:
        field_copy = field.replace(".", "__")
        rwork_type_assign = rwork_type_assign.order_by(field_copy)
        template = "base/rotating_work_type/htmx/group_by.html"

    rwork_type_assign = sortby(request, rwork_type_assign, "orderby")
    assign_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                rwork_type_assign, request.GET.get("page")
            ).object_list
        ]
    )

    return render(
        request,
        template,
        {
            "rwork_type_assign": paginator_qry(
                rwork_type_assign, request.GET.get("page")
            ),
            "pd": previous_data,
            "filter_dict": data_dict,
            "assign_ids": assign_ids,
            "field": field,
        },
    )


@login_required
@manager_can_enter("base.view_rotatingworktypeassign")
def rotating_work_individual_view(request, instance_id):
    """
    This view is used render detailed view of the rotating work type assign
    """
    instance = RotatingWorkTypeAssign.objects.get(id=instance_id)
    context = {"instance": instance}
    assign_ids_json = request.GET.get("instances_ids")
    if assign_ids_json:
        assign_ids = json.loads(assign_ids_json)
        previous_id, next_id = closest_numbers(assign_ids, instance_id)
        context["previous"] = previous_id
        context["next"] = next_id
        context["assign_ids"] = assign_ids_json
    return render(request, "base/rotating_work_type/individual_view.html", context)


@login_required
@manager_can_enter("base.change_rotatingworktypeassign")
def rotating_work_type_assign_update(request, id):
    """
    This method is used to update rotating work type instance
    """

    rotating_work_type_assign_obj = RotatingWorkTypeAssign.objects.get(id=id)
    form = RotatingWorkTypeAssignUpdateForm(instance=rotating_work_type_assign_obj)
    form = choosesubordinates(request, form, "base.change_rotatingworktypeassign")
    if request.method == "POST":
        form = RotatingWorkTypeAssignUpdateForm(
            request.POST, instance=rotating_work_type_assign_obj
        )
        form = choosesubordinates(request, form, "base.change_rotatingworktypeassign")
        if form.is_valid():
            form.save()
            messages.success(request, _("Rotating work type assign updated."))
            response = render(
                request,
                "base/rotating_work_type/htmx/rotating_work_type_assign_update_form.html",
                {"update_form": form},
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(
        request,
        "base/rotating_work_type/htmx/rotating_work_type_assign_update_form.html",
        {"update_form": form},
    )


@login_required
@manager_can_enter("base.change_rotatingworktypeassign")
def rotating_work_type_assign_export(request):
    return export_data(
        request=request,
        model=RotatingWorkTypeAssign,
        filter_class=RotatingWorkTypeAssignFilter,
        form_class=RotatingWorkTypeAssignExportForm,
        file_name="Rotating_work_type_assign",
    )


@login_required
@manager_can_enter("base.change_rotatingworktypeassign")
def rotating_work_type_assign_archive(request, id):
    """
    This method is used to archive or un-archive rotating work type assigns
    """
    rwork_type = RotatingWorkTypeAssign.objects.get(id=id)
    employees_rwork_types = RotatingWorkTypeAssign.objects.filter(
        is_active=True, employee_id=rwork_type.employee_id
    )
    flag = False
    if len(employees_rwork_types) < 1:
        rwork_type.is_active = True
        flag = True

    message = _("un-archived")
    if request.GET.get("is_active") == "False":
        rwork_type.is_active = False
        message = _("archived")
        flag = True
    rwork_type.save()
    if flag:
        messages.success(
            request, _("Rotating shift assign is {message}").format(message=message)
        )
    else:
        messages.error(request, "Already on record is active")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@manager_can_enter("base.change_rotatingworktypeassign")
def rotating_work_type_assign_bulk_archive(request):
    """
    This method is used to archive/un-archive bulk rotating work type assigns
    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    is_active = True
    message = _("un-archived")
    if request.GET.get("is_active") == "False":
        is_active = False
        message = _("archived")
    for id in ids:
        # check permission right here...
        rwork_type_assign = RotatingWorkTypeAssign.objects.get(id=id)
        employees_rwork_type_assign = RotatingWorkTypeAssign.objects.filter(
            is_active=True, employee_id=rwork_type_assign.employee_id
        )
        flag = True
        if is_active:
            if len(employees_rwork_type_assign) < 1:
                flag = False
                rwork_type_assign.is_active = is_active
        else:
            flag = False
            rwork_type_assign.is_active = is_active
        rwork_type_assign.save()
        if not flag:
            messages.success(
                request,
                _("Rotating work type for {employee_id} is {message}").format(
                    employee_id=rwork_type_assign.employee_id, message=message
                ),
            )
        else:
            messages.error(
                request,
                _("Rotating work type for {employee_id} is already exists").format(
                    employee_id=rwork_type_assign.employee_id,
                ),
            )
    return JsonResponse({"message": "Success"})


@login_required
@permission_required("base.delete_rotatingworktypeassign")
def rotating_work_type_assign_bulk_delete(request):
    """
    This method is used to archive/un-archive bulk rotating work type assigns
    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    for id in ids:
        try:
            rwork_type_assign = RotatingWorkTypeAssign.objects.get(id=id)
            rwork_type_assign.delete()
            messages.success(
                request,
                _("{employee} deleted.").format(employee=rwork_type_assign.employee_id),
            )
        except RotatingWorkTypeAssign.DoesNotExist:
            messages.error(request, _("{rwork_type_assign} not found."))
        except ProtectedError:
            messages.error(
                request,
                _("You cannot delete {rwork_type_assign}").format(
                    rwork_type_assign=rwork_type_assign
                ),
            )
    return JsonResponse({"message": "Success"})


@login_required
@permission_required("base.delete_rotatingworktypeassign")
@require_http_methods(["POST"])
def rotating_work_type_assign_delete(request, id):
    """
    This method is used to delete rotating work type
    """
    try:
        rotating_work_type_assign_obj = RotatingWorkTypeAssign.objects.get(
            id=id
        ).delete()
        messages.success(request, _("Rotating work type assign deleted."))
    except RotatingWorkTypeAssign.DoesNotExist:
        messages.error(request, _("Rotating work type assign not found."))
    except ProtectedError:
        messages.error(request, _("You cannot delete this rotating work type."))

    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@permission_required("base.view_employeetype")
def employee_type_view(request):
    """
    This method is used to view employee type
    """

    types = EmployeeType.objects.all()
    return render(
        request,
        "base/employee_type/employee_type.html",
        {
            "employee_types": types,
        },
    )


@login_required
@permission_required("base.add_employeetype")
def employee_type_create(request):
    """
    This method is used to create employee type
    """
    dynamic = request.GET.get("dynamic")
    form = EmployeeTypeForm()
    types = EmployeeType.objects.all()
    if request.method == "POST":
        form = EmployeeTypeForm(request.POST)
        if form.is_valid():
            form.save()
            form = EmployeeTypeForm()
            messages.success(request, _("Employee type created."))
            return HttpResponse("<script>window.location.reload();</script>")
    return render(
        request,
        "base/employee_type/employee_type_form.html",
        {"form": form, "employee_types": types, "dynamic": dynamic},
    )


@login_required
@permission_required("base.change_employeetype")
def employee_type_update(request, id, **kwargs):
    """
    This method is used to update employee type instance
    args:
        id : employee type instance id

    """

    employee_type = EmployeeType.objects.get(id=id)
    form = EmployeeTypeForm(instance=employee_type)
    if request.method == "POST":
        form = EmployeeTypeForm(request.POST, instance=employee_type)
        if form.is_valid():
            form.save()
            messages.success(request, _("Employee type updated."))
            return HttpResponse("<script>window.location.reload();</script>")
    return render(
        request,
        "base/employee_type/employee_type_form.html",
        {"form": form, "employee_type": employee_type},
    )


@login_required
@permission_required("base.view_employeeshift")
def employee_shift_view(request):
    """
    This method is used to view employee shift
    """

    shifts = EmployeeShift.objects.all()
    grace_times = GraceTime.objects.all().exclude(is_default=True)
    return render(
        request, "base/shift/shift.html", {"shifts": shifts, "grace_times": grace_times}
    )


@login_required
@permission_required("base.add_employeeshift")
def employee_shift_create(request):
    """
    This method is used to create employee shift
    """
    dynamic = request.GET.get("dynamic")
    form = EmployeeShiftForm()
    shifts = EmployeeShift.objects.all()
    if request.method == "POST":
        form = EmployeeShiftForm(request.POST)
        if form.is_valid():
            form.save()
            form = EmployeeShiftForm()
            messages.success(
                request, _("Employee Shift has been created successfully!")
            )
            return HttpResponse("<script>window.location.reload();</script>")
    return render(
        request,
        "base/shift/shift_form.html",
        {"form": form, "shifts": shifts, "dynamic": dynamic},
    )


@login_required
@permission_required("base.change_employeeshiftupdate")
def employee_shift_update(request, id, **kwargs):
    """
    This method is used to update employee shift instance
    args:
        id  : employee shift id

    """
    employee_shift = EmployeeShift.objects.get(id=id)
    form = EmployeeShiftForm(instance=employee_shift)
    if request.method == "POST":
        form = EmployeeShiftForm(request.POST, instance=employee_shift)
        if form.is_valid():
            form.save()
            messages.success(request, _("Shift updated"))
            return HttpResponse("<script>window.location.reload();</script>")
    return render(
        request, "base/shift/shift_form.html", {"form": form, "shift": employee_shift}
    )


@login_required
@permission_required("base.view_employeeshiftschedule")
def employee_shift_schedule_view(request):
    """
    This method is used to view schedule for shift
    """
    shift_schedule = False
    if EmployeeShiftSchedule.objects.exists():
        shift_schedule = True
    shifts = EmployeeShift.objects.all()

    return render(
        request,
        "base/shift/schedule.html",
        {"shifts": shifts, "shift_schedule": shift_schedule},
    )


@login_required
@permission_required("base.add_employeeshiftschedule")
def employee_shift_schedule_create(request):
    """
    This method is used to create schedule for shift
    """

    form = EmployeeShiftScheduleForm()
    shifts = EmployeeShift.objects.all()
    if request.method == "POST":
        form = EmployeeShiftScheduleForm(request.POST)
        if form.is_valid():
            form.save()
            form = EmployeeShiftScheduleForm()
            messages.success(
                request, _("Employee Shift Schedule has been created successfully!")
            )
            return HttpResponse("<script>window.location.reload();</script>")

    return render(
        request, "base/shift/schedule_form.html", {"form": form, "shifts": shifts}
    )


@login_required
@permission_required("base.change_employeeshiftschedule")
def employee_shift_schedule_update(request, id, **kwargs):
    """
    This method is used to update employee shift instance
    args:
        id : employee shift instance id
    """

    employee_shift_schedule = EmployeeShiftSchedule.objects.get(id=id)
    form = EmployeeShiftScheduleUpdateForm(instance=employee_shift_schedule)
    if request.method == "POST":
        form = EmployeeShiftScheduleUpdateForm(
            request.POST, instance=employee_shift_schedule
        )
        if form.is_valid():
            form.save()
            messages.success(request, _("Shift schedule created."))
            return HttpResponse("<script>window.location.reload();</script>")
    return render(
        request,
        "base/shift/schedule_form.html",
        {"form": form, "shift_schedule": employee_shift_schedule},
    )


@login_required
@permission_required("base.view_rotatingshift")
def rotating_shift_view(request):
    """
    This method is used to view rotating shift
    """

    return render(
        request,
        "base/rotating_shift/rotating_shift.html",
        {"rshifts": RotatingShift.objects.all()},
    )


@login_required
@permission_required("base.add_rotatingshift")
def rotating_shift_create(request):
    """
    This method is used to create rotating shift
    """

    form = RotatingShiftForm()
    if request.method == "POST":
        form = RotatingShiftForm(request.POST)
        if form.is_valid():
            form.save()
            form = RotatingShiftForm()
            messages.success(request, _("Rotating shift created."))
            return HttpResponse("<script>window.location.reload();</script>")

    return render(
        request,
        "base/rotating_shift/htmx/rotating_shift_form.html",
        {"form": form, "rshifts": RotatingShift.objects.all()},
    )


@login_required
@permission_required("base.change_rotatingshift")
def rotating_shift_update(request, id, **kwargs):
    """
    This method is used to update rotating shift instance
    args:
        id : rotating shift instance id
    """

    rotating_shift = RotatingShift.objects.get(id=id)
    form = RotatingShiftForm(instance=rotating_shift)
    if request.method == "POST":
        form = RotatingShiftForm(request.POST, instance=rotating_shift)
        if form.is_valid():
            form.save()
            form = RotatingShiftForm()
            messages.success(request, _("Rotating shift updated."))
            return HttpResponse("<script>window.location.reload();</script>")
    return render(
        request,
        "base/rotating_shift/htmx/rotating_shift_form.html",
        {
            "form": form,
            "rshift": rotating_shift,
        },
    )


@login_required
@manager_can_enter("base.view_rotatingshiftassign")
def rotating_shift_assign(request):
    """
    This method is used to assign rotating shift
    """
    form = RotatingShiftAssignForm()
    form = choosesubordinates(request, form, "base.add_rotatingshiftassign")
    filter = RotatingShiftAssignFilters(
        queryset=RotatingShiftAssign.objects.filter(is_active=True)
    )
    rshift_assign = filter.qs
    rshift_all = RotatingShiftAssign.objects.all()

    rshift_assign = filtersubordinates(
        request, rshift_assign, "base.view_rotatingshiftassign"
    )
    rshift_assign = rshift_assign.filter(employee_id__is_active=True)
    assign_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                rshift_assign, request.GET.get("page")
            ).object_list
        ]
    )

    return render(
        request,
        "base/rotating_shift/rotating_shift_assign.html",
        {
            "form": form,
            "f": filter,
            "export_filter": RotatingShiftAssignFilters(),
            "export_columns": RotatingShiftAssignExportForm(),
            "rshift_assign": paginator_qry(rshift_assign, request.GET.get("page")),
            "assign_ids": assign_ids,
            "rshift_all": rshift_all,
            "gp_fields": RotatingShiftRequestReGroup.fields,
        },
    )


@login_required
@manager_can_enter("base.add_rotatingshiftassign")
def rotating_shift_assign_add(request):
    """
    This method is used to add rotating shift assign
    """
    form = RotatingShiftAssignForm()
    if request.GET.get("emp_id"):
        employee = request.GET.get("emp_id")
        form = RotatingShiftAssignForm(initial={"employee_id": employee})
    form = choosesubordinates(request, form, "base.add_rotatingshiftassign")
    if request.method == "POST":
        form = RotatingShiftAssignForm(request.POST)
        form = choosesubordinates(request, form, "base.add_rotatingshiftassign")
        if form.is_valid():
            form.save()
            employee_ids = request.POST.getlist("employee_id")
            employees = Employee.objects.filter(id__in=employee_ids).select_related(
                "employee_user_id"
            )
            users = [employee.employee_user_id for employee in employees]
            notify.send(
                request.user.employee_get,
                recipient=users,
                verb="You are added to rotating shift",
                verb_ar="تمت إضافتك إلى وردية الدورية",
                verb_de="Sie werden der rotierenden Arbeitsschicht hinzugefügt",
                verb_es="Estás agregado a turno rotativo",
                verb_fr="Vous êtes ajouté au quart de travail rotatif",
                icon="infinite",
                redirect="/employee/employee-profile/",
            )

            messages.success(request, _("Rotating shift assigned."))
            response = render(
                request,
                "base/rotating_shift/htmx/rotating_shift_assign_form.html",
                {"form": form},
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(
        request,
        "base/rotating_shift/htmx/rotating_shift_assign_form.html",
        {"form": form},
    )


@login_required
@manager_can_enter("base.view_rotatingshiftassign")
def rotating_shift_assign_view(request):
    """
    This method renders all instance of rotating shift assign to a template
    """
    previous_data = request.GET.urlencode()
    rshift_assign = RotatingShiftAssignFilters(request.GET).qs
    field = request.GET.get("field")
    if (
        request.GET.get("is_active") is None
        or request.GET.get("is_active") == "unknown"
    ):
        rshift_assign = rshift_assign.filter(is_active=True)
    rshift_assign = filtersubordinates(
        request, rshift_assign, "base.view_rotatingshiftassign"
    )
    data_dict = parse_qs(previous_data)
    get_key_instances(RotatingShiftAssign, data_dict)
    template = "base/rotating_shift/rotating_shift_assign_view.html"
    if field != "" and field is not None:
        field_copy = field.replace(".", "__")
        rshift_assign = rshift_assign.order_by(field_copy)
        template = "base/rotating_shift/htmx/group_by.html"
    rshift_assign = sortby(request, rshift_assign, "orderby")
    assign_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                rshift_assign, request.GET.get("page")
            ).object_list
        ]
    )
    return render(
        request,
        template,
        {
            "rshift_assign": paginator_qry(rshift_assign, request.GET.get("page")),
            "pd": previous_data,
            "filter_dict": data_dict,
            "assign_ids": assign_ids,
            "field": field,
        },
    )


@login_required
@manager_can_enter("base.view_rotatingworktypeassign")
def rotating_shift_individual_view(request, instance_id):
    """
    This view is used render detailed view of the rotating shit assign
    """
    instance = RotatingShiftAssign.objects.get(id=instance_id)
    context = {"instance": instance}
    assign_ids_json = request.GET.get("instances_ids")
    if assign_ids_json:
        assign_ids = json.loads(assign_ids_json)
        previous_id, next_id = closest_numbers(assign_ids, instance_id)
        context["previous"] = previous_id
        context["next"] = next_id
        context["assign_ids"] = assign_ids
    return render(request, "base/rotating_shift/individual_view.html", context)


@login_required
@manager_can_enter("base.change_rotatingshiftassign")
def rotating_shift_assign_update(request, id):
    """
    This method is used to update rotating shift assign instance
    args:
        id : rotating shift assign instance id

    """
    rotating_shift_assign_obj = RotatingShiftAssign.objects.get(id=id)
    form = RotatingShiftAssignUpdateForm(instance=rotating_shift_assign_obj)
    form = choosesubordinates(request, form, "base.change_rotatingshiftassign")
    if request.method == "POST":
        form = RotatingShiftAssignUpdateForm(
            request.POST, instance=rotating_shift_assign_obj
        )
        form = choosesubordinates(request, form, "base.change_rotatingshiftassign")
        if form.is_valid():
            form.save()
            messages.success(request, _("Rotating shift assign updated."))
            response = render(
                request,
                "base/rotating_shift/htmx/rotating_shift_assign_update_form.html",
                {
                    "update_form": form,
                },
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(
        request,
        "base/rotating_shift/htmx/rotating_shift_assign_update_form.html",
        {
            "update_form": form,
        },
    )


@login_required
@manager_can_enter("base.change_rotatingshiftassign")
def rotating_shift_assign_export(request):
    return export_data(
        request=request,
        model=RotatingShiftAssign,
        filter_class=RotatingShiftAssignFilters,
        form_class=RotatingShiftAssignExportForm,
        file_name="Rotating_shift_assign_export",
    )


@login_required
@manager_can_enter("base.change_rotatingshiftassign")
def rotating_shift_assign_archive(request, id):
    """
    This method is used to archive and unarchive rotating shift assign records
    """
    rshift = RotatingShiftAssign.objects.get(id=id)
    employees_rshift_assign = RotatingShiftAssign.objects.filter(
        is_active=True, employee_id=rshift.employee_id
    )
    flag = False
    if len(employees_rshift_assign) < 1:
        rshift.is_active = True
        flag = True
    message = _("un-archived")
    if request.GET.get("is_active") == "False":
        rshift.is_active = False
        flag = True
        message = _("archived")
    rshift.save()
    if flag:
        messages.success(
            request, _("Rotating shift assign is {message}").format(message=message)
        )
    else:
        messages.error(request, "Already on record is active")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@manager_can_enter("base.change_rotatingshiftassign")
def rotating_shift_assign_bulk_archive(request):
    """
    This method is used to archive/un-archive bulk rotating shift assigns
    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    is_active = True
    message = _("un-archived")
    if request.GET.get("is_active") == "False":
        is_active = False
        message = _("archived")
    for id in ids:
        # check permission right here...
        rshift_assign = RotatingShiftAssign.objects.get(id=id)
        employees_rshift_assign = RotatingShiftAssign.objects.filter(
            is_active=True, employee_id=rshift_assign.employee_id
        )
        flag = True
        if is_active:
            if len(employees_rshift_assign) < 1:
                flag = False
                rshift_assign.is_active = is_active
        else:
            flag = False
            rshift_assign.is_active = is_active
        rshift_assign.save()
        if not flag:
            messages.success(
                request,
                _("Rotating shift for {employee} is {message}").format(
                    employee=rshift_assign.employee_id, message=message
                ),
            )
        else:
            messages.error(
                request,
                _("Rotating shift for {employee} is already exists").format(
                    employee=rshift_assign.employee_id
                ),
            )
    return JsonResponse({"message": "Success"})


@login_required
@permission_required("base.delete_rotatingshiftassign")
def rotating_shift_assign_bulk_delete(request):
    """
    This method is used to bulk delete for rotating shift assign
    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    for id in ids:
        try:
            rshift_assign = RotatingShiftAssign.objects.get(id=id)
            rshift_assign.delete()
            messages.success(
                request,
                _("{employee} assign deleted.").format(
                    employee=rshift_assign.employee_id
                ),
            )
        except RotatingShiftAssign.DoesNotExist:
            messages.error(request, _("{rshift_assign} not found."))
        except ProtectedError:
            messages.error(
                request,
                _("You cannot delete {rshift_assign}").format(
                    rshift_assign=rshift_assign
                ),
            )
    return JsonResponse({"message": "Success"})


@login_required
@permission_required("base.delete_rotatingshiftassign")
@require_http_methods(["POST"])
def rotating_shift_assign_delete(request, id):
    """
    This method is used to delete rotating shift assign instance
    args:
        id : rotating shift assign instance id
    """
    try:
        rotating_shift_assign_obj = RotatingShiftAssign.objects.get(id=id).delete()
        messages.success(request, _("Rotating shift assign deleted."))
    except RotatingShiftAssign.DoesNotExist:
        messages.error(request, _("Rotating shift assign not found."))
    except ProtectedError:
        messages.error(request, _("You cannot delete this rotating shift assign."))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


def get_models_in_app(app_name):
    """
    get app models
    """
    try:
        app_config = apps.get_app_config(app_name)
        models = app_config.get_models()
        return models
    except LookupError:
        return []


@login_required
@manager_can_enter("auth.view_permission")
def employee_permission_assign(request):
    """
    This method is used to assign permissions to employee user
    """

    context = {}
    template = "base/auth/permission.html"
    if request.GET.get("profile_tab"):
        template = "base/auth/permission_accordion.html"
        employees = Employee.objects.filter(id=request.GET["employee_id"]).distinct()
    else:
        employees = Employee.objects.filter(
            employee_user_id__user_permissions__isnull=False
        ).distinct()
        context["show_assign"] = True
    permissions = []
    apps = [
        "base",
        "recruitment",
        "employee",
        "leave",
        "pms",
        "onboarding",
        "asset",
        "attendance",
        "payroll",
        "auth",
        "offboarding",
        "horilla_documents",
        "helpdesk",
    ]
    for app_name in apps:
        app_models = []
        for model in get_models_in_app(app_name):
            app_models.append(
                {
                    "verbose_name": model._meta.verbose_name.capitalize(),
                    "model_name": model._meta.model_name,
                }
            )
        permissions.append({"app": app_name.capitalize(), "app_models": app_models})
    context["permissions"] = permissions
    context["employees"] = paginator_qry(employees, request.GET.get("page"))
    return render(
        request,
        template,
        context,
    )


@login_required
@permission_required("view_permissions")
def employee_permission_search(request, codename=None, uid=None):
    """
    This method renders template to view all instances of user permissions
    """
    context = {}
    template = "base/auth/permission_lines.html"
    employees = EmployeeFilter(request.GET).qs
    if request.GET.get("profile_tab"):
        template = "base/auth/permission_accordion.html"
        employees = employees.filter(id=request.GET["employee_id"]).distinct()
    else:
        employees = employees.filter(
            employee_user_id__user_permissions__isnull=False
        ).distinct()
        context["show_assign"] = True
    permissions = []
    apps = [
        "base",
        "recruitment",
        "employee",
        "leave",
        "pms",
        "onboarding",
        "asset",
        "attendance",
        "payroll",
        "auth",
        "offboarding",
        "horilla_documents",
        "helpdesk",
    ]
    for app_name in apps:
        app_models = []
        for model in get_models_in_app(app_name):
            app_models.append(
                {
                    "verbose_name": model._meta.verbose_name.capitalize(),
                    "model_name": model._meta.model_name,
                }
            )
        permissions.append({"app": app_name.capitalize(), "app_models": app_models})
    context["permissions"] = permissions
    context["employees"] = paginator_qry(employees, request.GET.get("page"))
    return render(
        request,
        template,
        context,
    )


# add_recruitment


@login_required
@require_http_methods(["POST"])
@permission_required("auth.add_permission")
def update_permission(
    request,
):
    """
    This method is used to remove user permission.
    """
    form = AssignPermission(request.POST)
    if form.is_valid():
        form.save()
        return JsonResponse({"message": "Updated the permissions", "type": "success"})
    if (
        form.data.get("employee")
        and Employee.objects.filter(id=form.data["employee"]).first()
    ):
        Employee.objects.filter(
            id=form.data["employee"]
        ).first().employee_user_id.user_permissions.clear()
        return JsonResponse({"message": "All permission cleared", "type": "info"})
    return JsonResponse({"message": "Something went wrong", "type": "danger"})


@login_required
@permission_required("auth.add_permission")
def permission_table(request):
    """
    This method is used to render the permission table
    """
    permissions = []
    apps = [
        "base",
        "recruitment",
        "employee",
        "leave",
        "pms",
        "onboarding",
        "asset",
        "attendance",
        "payroll",
        "auth",
        "offboarding",
        "horilla_documents",
        "helpdesk",
    ]
    form = AssignPermission()
    for app_name in apps:
        app_models = []
        for model in get_models_in_app(app_name):
            app_models.append(
                {
                    "verbose_name": model._meta.verbose_name.capitalize(),
                    "model_name": model._meta.model_name,
                }
            )
        permissions.append({"app": app_name.capitalize(), "app_models": app_models})
    if request.method == "POST":
        form = AssignPermission(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Employee permission assigned."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/auth/permission_assign.html",
        {
            "permissions": permissions,
            "form": form,
        },
    )


@login_required
def work_type_request_view(request):
    """
    This method renders template to  view all work type requests
    """
    previous_data = request.GET.urlencode()
    employee = Employee.objects.filter(employee_user_id=request.user).first()
    work_type_requests = filtersubordinates(
        request, WorkTypeRequest.objects.all(), "base.add_worktyperequest"
    )
    work_type_requests = work_type_requests | WorkTypeRequest.objects.filter(
        employee_id=employee
    )
    work_type_requests = work_type_requests.filter(employee_id__is_active=True)
    requests_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                work_type_requests, request.GET.get("page")
            ).object_list
        ]
    )
    f = WorkTypeRequestFilter(request.GET, queryset=work_type_requests)
    data_dict = parse_qs(previous_data)
    get_key_instances(WorkTypeRequest, data_dict)
    export_filter = WorkTypeRequestFilter()
    export_fields = WorkTypeRequestColumnForm()
    form = WorkTypeRequestForm()
    form = choosesubordinates(
        request,
        form,
        "base.add_worktypereqeust",
    )
    form = include_employee_instance(request, form)
    return render(
        request,
        "work_type_request/work_type_request_view.html",
        {
            "data": paginator_qry(f.qs, request.GET.get("page")),
            "f": f,
            "form": form,
            "export_filter": export_filter,
            "filter_dict": data_dict,
            "export_fields": export_fields,
            "requests_ids": requests_ids,
            "gp_fields": WorkTypeRequestReGroup.fields,
        },
    )


@login_required
@manager_can_enter("base.view_worktyperequest")
def work_type_request_export(request):
    return export_data(
        request,
        WorkTypeRequest,
        WorkTypeRequestColumnForm,
        WorkTypeRequestFilter,
        "Work_type_request",
    )


@login_required
def work_type_request_search(request):
    """
    This method is used to search work type request.
    """
    employee = Employee.objects.filter(employee_user_id=request.user).first()
    previous_data = request.GET.urlencode()
    field = request.GET.get("field")
    f = WorkTypeRequestFilter(request.GET)
    work_typ_requests = filtersubordinates(request, f.qs, "base.add_worktyperequest")
    if set(WorkTypeRequest.objects.filter(employee_id=employee)).issubset(set(f.qs)):
        work_typ_requests = work_typ_requests | WorkTypeRequest.objects.filter(
            employee_id=employee
        )
    work_typ_requests = sortby(request, work_typ_requests, "orderby")
    template = "work_type_request/htmx/requests.html"
    if field != "" and field is not None:
        field_copy = field.replace(".", "__")
        work_typ_requests = work_typ_requests.order_by(f"-{field_copy}")
        template = "work_type_request/htmx/group_by.html"

    requests_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                work_typ_requests, request.GET.get("page")
            ).object_list
        ]
    )
    data_dict = parse_qs(previous_data)
    get_key_instances(WorkTypeRequest, data_dict)
    return render(
        request,
        template,
        {
            "data": paginator_qry(work_typ_requests, request.GET.get("page")),
            "pd": previous_data,
            "filter_dict": data_dict,
            "requests_ids": requests_ids,
            "field": field,
        },
    )


@login_required
def work_type_request(request):
    """
    This method is used to create request for work type  .
    """
    form = WorkTypeRequestForm()
    employee = request.user.employee_get.id
    if request.GET.get("emp_id"):
        employee = request.GET.get("emp_id")
    form = WorkTypeRequestForm(initial={"employee_id": employee})
    form = choosesubordinates(
        request,
        form,
        "base.add_worktyperequest",
    )
    form = include_employee_instance(request, form)

    f = WorkTypeRequestFilter()
    if request.method == "POST":
        form = WorkTypeRequestForm(request.POST)
        form = choosesubordinates(
            request,
            form,
            "base.add_worktyperequest",
        )
        form = include_employee_instance(request, form)
        response = render(
            request, "work_type_request/request_form.html", {"form": form, "f": f}
        )
        if form.is_valid():
            instance = form.save()
            try:
                notify.send(
                    instance.employee_id,
                    recipient=(
                        instance.employee_id.employee_work_info.reporting_manager_id.employee_user_id
                    ),
                    verb=f"You have new work type request to \
                            validate for {instance.employee_id}",
                    verb_ar=f"لديك طلب نوع وظيفة جديد للتحقق من \
                            {instance.employee_id}",
                    verb_de=f"Sie haben eine neue Arbeitstypanfrage zur \
                            Validierung für {instance.employee_id}",
                    verb_es=f"Tiene una nueva solicitud de tipo de trabajo para \
                            validar para {instance.employee_id}",
                    verb_fr=f"Vous avez une nouvelle demande de type de travail\
                            à valider pour {instance.employee_id}",
                    icon="information",
                    redirect=f"/employee/work-type-request-view?id={instance.id}",
                )
            except Exception as error:
                pass
            messages.success(request, _("Work type request added."))
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )

    return render(
        request, "work_type_request/request_form.html", {"form": form, "f": f}
    )


@login_required
def work_type_request_cancel(request, id):
    """
    This method is used to cancel work type request
    args:
        id  : work type request id

    """
    work_type_request = WorkTypeRequest.objects.get(id=id)
    if (
        is_reportingmanger(request, work_type_request)
        or request.user.has_perm("base.cancel_worktyperequest")
        or work_type_request.employee_id == request.user.employee_get
        and work_type_request.approved == False
    ):
        work_type_request.canceled = True
        work_type_request.approved = False
        work_type_request.employee_id.employee_work_info.work_type_id = (
            work_type_request.previous_work_type_id
        )
        work_type_request.employee_id.employee_work_info.save()
        work_type_request.save()
        messages.success(request, _("Work type request has been rejected."))
        notify.send(
            request.user.employee_get,
            recipient=work_type_request.employee_id.employee_user_id,
            verb="Your work type request has been rejected.",
            verb_ar="تم إلغاء طلب نوع وظيفتك",
            verb_de="Ihre Arbeitstypanfrage wurde storniert",
            verb_es="Su solicitud de tipo de trabajo ha sido cancelada",
            verb_fr="Votre demande de type de travail a été annulée",
            redirect=f"/employee/work-type-request-view?id={work_type_request.id}",
            icon="close",
        )
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
    return HttpResponse("You dont have permission")


@login_required
@manager_can_enter("base.change_worktyperequest")
def work_type_request_bulk_cancel(request):
    """
    This method is used to cancel a bunch work type request
    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    result = False
    for id in ids:
        work_type_request = WorkTypeRequest.objects.get(id=id)
        if (
            is_reportingmanger(request, work_type_request)
            or request.user.has_perm("base.cancel_worktyperequest")
            or work_type_request.employee_id == request.user.employee_get
            and work_type_request.approved == False
        ):
            work_type_request.canceled = True
            work_type_request.approved = False
            work_type_request.employee_id.employee_work_info.work_type_id = (
                work_type_request.previous_work_type_id
            )
            work_type_request.employee_id.employee_work_info.save()
            work_type_request.save()
            messages.success(request, _("Work type request has been canceled."))
            notify.send(
                request.user.employee_get,
                recipient=work_type_request.employee_id.employee_user_id,
                verb="Your work type request has been canceled.",
                verb_ar="تم إلغاء طلب نوع وظيفتك.",
                verb_de="Ihre Arbeitstypanfrage wurde storniert.",
                verb_es="Su solicitud de tipo de trabajo ha sido cancelada.",
                verb_fr="Votre demande de type de travail a été annulée.",
                redirect=f"/employee/work-type-request-view?id={work_type_request.id}",
                icon="close",
            )
            result = True
    return JsonResponse({"result": result})


@login_required
def work_type_request_approve(request, id):
    """
    This method is used to approve requested work type
    """

    work_type_request = WorkTypeRequest.objects.get(id=id)
    if (
        is_reportingmanger(request, work_type_request)
        or request.user.has_perm("approve_worktyperequest")
        or request.user.has_perm("change_worktyperequest")
        and not work_type_request.approved
    ):
        """
        Here the request will be approved, can send mail right here
        """
        if not work_type_request.is_any_work_type_request_exists():
            work_type_request.approved = True
            work_type_request.canceled = False
            work_type_request.save()
            messages.success(request, _("Work type request has been approved."))
            notify.send(
                request.user.employee_get,
                recipient=work_type_request.employee_id.employee_user_id,
                verb="Your work type request has been approved.",
                verb_ar="تمت الموافقة على طلب نوع وظيفتك.",
                verb_de="Ihre Arbeitstypanfrage wurde genehmigt.",
                verb_es="Su solicitud de tipo de trabajo ha sido aprobada.",
                verb_fr="Votre demande de type de travail a été approuvée.",
                redirect=f"/employee/work-type-request-view?id={work_type_request.id}",
                icon="checkmark",
            )

            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

        else:
            messages.error(
                request, _("A shift request already exists during this time period.")
            )
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
    return HttpResponse("You Do nt Have Permission")


@login_required
def work_type_request_bulk_approve(request):
    """
    This method is used to approve bulk of requested work type
    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    result = False
    for id in ids:
        work_type_request = WorkTypeRequest.objects.get(id=id)
        if (
            is_reportingmanger(request, work_type_request)
            or request.user.has_perm("approve_worktyperequest")
            or request.user.has_perm("change_worktyperequest")
            and not work_type_request.approved
        ):
            # """
            # Here the request will be approved, can send mail right here
            # """
            work_type_request.approved = True
            work_type_request.canceled = False
            employee_work_info = work_type_request.employee_id.employee_work_info
            employee_work_info.work_type_id = work_type_request.work_type_id
            employee_work_info.save()
            work_type_request.save()
            messages.success(request, _("Work type request has been approved."))
            notify.send(
                request.user.employee_get,
                recipient=work_type_request.employee_id.employee_user_id,
                verb="Your work type request has been approved.",
                verb_ar="تمت الموافقة على طلب نوع وظيفتك.",
                verb_de="Ihre Arbeitstypanfrage wurde genehmigt.",
                verb_es="Su solicitud de tipo de trabajo ha sido aprobada.",
                verb_fr="Votre demande de type de travail a été approuvée.",
                redirect=f"/employee/work-type-request-view?id={work_type_request.id}",
                icon="checkmark",
            )
            result = True
    return JsonResponse({"result": result})


@login_required
@work_type_request_change_permission()
def work_type_request_update(request, work_type_request_id):
    """
    This method is used to update work type request instance
    args:
        id : work type request instance id

    """
    work_type_request = WorkTypeRequest.objects.get(id=work_type_request_id)
    form = WorkTypeRequestForm(instance=work_type_request)
    form = choosesubordinates(request, form, "base.change_worktyperequest")
    form = include_employee_instance(request, form)
    if request.method == "POST":
        response = render(
            request,
            "work_type_request/request_update_form.html",
            {
                "form": form,
            },
        )
        form = WorkTypeRequestForm(request.POST, instance=work_type_request)
        form = choosesubordinates(request, form, "base.change_worktyperequest")
        form = include_employee_instance(request, form)
        if form.is_valid():
            form.save()
            messages.success(request, _("Request Updated Successfully"))
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )

    return render(request, "work_type_request/request_update_form.html", {"form": form})


@login_required
@require_http_methods(["POST"])
def work_type_request_delete(request, id):
    """
    This method is used to delete work type request
    args:
        id : work type request instance id

    """
    try:
        work_type_request = WorkTypeRequest.objects.get(id=id)
        employee = work_type_request.employee_id.employee_user_id
        messages.success(request, _("Work type request deleted."))
        work_type_request.delete()
        notify.send(
            request.user.employee_get,
            recipient=employee,
            verb="Your work type request has been deleted.",
            verb_ar="تم حذف طلب نوع وظيفتك.",
            verb_de="Ihre Arbeitstypanfrage wurde gelöscht.",
            verb_es="Su solicitud de tipo de trabajo ha sido eliminada.",
            verb_fr="Votre demande de type de travail a été supprimée.",
            redirect="#",
            icon="trash",
        )
    except WorkTypeRequest.DoesNotExist:
        messages.error(request, _("Work type request not found."))
    except ProtectedError:
        messages.error(request, _("You cannot delete this work type request."))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def work_type_request_single_view(request, work_type_request_id):
    """
    This method is used to view details of an work type request
    """
    work_type_request = WorkTypeRequest.objects.get(id=work_type_request_id)
    context = {
        "work_type_request": work_type_request,
        "dashboard": request.GET.get("dashboard"),
    }
    requests_ids_json = request.GET.get("instances_ids")
    if requests_ids_json:
        requests_ids = json.loads(requests_ids_json)
        previous_id, next_id = closest_numbers(requests_ids, work_type_request_id)
        context["requests_ids"] = requests_ids_json
        context["previous"] = previous_id
        context["next"] = next_id
    return render(
        request,
        "work_type_request/htmx/work_type_request_single_view.html",
        context,
    )


@login_required
@permission_required("base.delete_worktyperequest")
@require_http_methods(["POST"])
def work_type_request_bulk_delete(request):
    """
    This method is used to delete work type request
    args:
        id : work type request instance id

    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    for id in ids:
        try:
            work_type_request = WorkTypeRequest.objects.get(id=id)
            user = work_type_request.employee_id.employee_user_id
            work_type_request.delete()
            messages.success(request, _("Work type request deleted."))
            notify.send(
                request.user.employee_get,
                recipient=user,
                verb="Your work type request has been deleted.",
                verb_ar="تم حذف طلب نوع وظيفتك.",
                verb_de="Ihre Arbeitstypanfrage wurde gelöscht.",
                verb_es="Su solicitud de tipo de trabajo ha sido eliminada.",
                verb_fr="Votre demande de type de travail a été supprimée.",
                redirect="#",
                icon="trash",
            )
        except WorkTypeRequest.DoesNotExist:
            messages.error(request, _("Work type request not found."))
        except ProtectedError:
            messages.error(
                request,
                _(
                    "You cannot delete {employee} work type request for the date {date}."
                ).format(
                    employee=work_type_request.employee_id,
                    date=work_type_request.requested_date,
                ),
            )
        result = True
    return JsonResponse({"result": result})


@login_required
def shift_request(request):
    """
    This method is used to create shift request
    """
    form = ShiftRequestForm()
    employee = request.user.employee_get.id
    if request.GET.get("emp_id"):
        employee = request.GET.get("emp_id")

    form = ShiftRequestForm(initial={"employee_id": employee})
    form = choosesubordinates(
        request,
        form,
        "base.add_shiftrequest",
    )
    form = include_employee_instance(request, form)
    f = ShiftRequestFilter()
    if request.method == "POST":
        form = ShiftRequestForm(request.POST)
        form = choosesubordinates(request, form, "base.add_shiftrequest")
        form = include_employee_instance(request, form)
        response = render(
            request,
            "shift_request/htmx/shift_request_create_form.html",
            {"form": form, "f": f},
        )
        if form.is_valid():
            instance = form.save()
            try:
                notify.send(
                    instance.employee_id,
                    recipient=(
                        instance.employee_id.employee_work_info.reporting_manager_id.employee_user_id
                    ),
                    verb=f"You have new shift request to approve \
                        for {instance.employee_id}",
                    verb_ar=f"لديك طلب وردية جديد للموافقة عليه لـ {instance.employee_id}",
                    verb_de=f"Sie müssen eine neue Schichtanfrage \
                        für {instance.employee_id} genehmigen",
                    verb_es=f"Tiene una nueva solicitud de turno para \
                        aprobar para {instance.employee_id}",
                    verb_fr=f"Vous avez une nouvelle demande de quart de\
                        travail à approuver pour {instance.employee_id}",
                    icon="information",
                    redirect=f"/employee/shift-request-view?id={instance.id}",
                )
            except Exception as e:
                pass
            messages.success(request, _("Request Added"))
            return HttpResponse(response.content.decode("utf-8")+ "<script>location.reload();</script>")
            # form = ShiftRequestForm()
            # if len(f.queryset) == 1:
            #     # Refresh the whole page to display the navbar otherwise refresh the requets container
            #     return HttpResponse(
            #         response.content.decode("utf-8")
            #         + "<script>location.reload();</script>"
            #     )
    return render(
        request,
        "shift_request/htmx/shift_request_create_form.html",
        {"form": form, "f": f},
    )


@login_required
def update_employee_allocation(request):

    shift = request.POST["shift_id"]

    shift = EmployeeShift.objects.filter(
        id=shift
    ).first()

    return JsonResponse(
        {
            "shift_name": shift.employee_shift,
            "employee_data":list(shift.employeeworkinformation_set.values_list("employee_id","employee_id__employee_first_name","employee_id__employee_last_name","employee_id__badge_id"))
        }
    )


@login_required
def shift_request_allocation(request):
    """
    This method is used to create shift request reallocation
    """
    form = ShiftAllocationForm()
    if request.GET.get("emp_id"):
        employee = request.GET.get("emp_id")
        form = ShiftAllocationForm(initial={"employee_id": employee})
    form = choosesubordinates(
        request,
        form,
        "base.add_shiftrequest",
    )
    form = include_employee_instance(request, form)
    f = ShiftRequestFilter()
    if request.method == "POST":
        form = ShiftAllocationForm(request.POST)
        form = choosesubordinates(request, form, "base.add_shiftrequest")
        form = include_employee_instance(request, form)
        response = render(
            request,
            "shift_request/htmx/shift_allocation_form.html",
            {"form": form, "f": f},
        )
        if form.is_valid():
            instance = form.save()
            reallocate_emp = form.cleaned_data['reallocate_to']
            try:
                notify.send(
                    instance.employee_id,
                    recipient=(
                        instance.employee_id.employee_work_info.reporting_manager_id.employee_user_id
                    ),
                    verb=f"You have a new shift reallocation request to approve for {instance.employee_id}.",
                    verb_ar=f"لديك طلب تخصيص جديد للورديات يتعين عليك الموافقة عليه لـ {instance.employee_id}.",
                    verb_de=f"Sie haben eine neue Anfrage zur Verschiebung der Schichtzuteilung zur Genehmigung für {instance.employee_id}.",
                    verb_es=f"Tienes una nueva solicitud de reasignación de turnos para aprobar para {instance.employee_id}.",
                    verb_fr=f"Vous avez une nouvelle demande de réaffectation de shift à approuver pour {instance.employee_id}.",
                    icon="information",
                    redirect=f"/employee/shift-request-view?id={instance.id}",
                )
            except Exception as e:
                pass

            try:
                notify.send(
                    instance.employee_id,
                    recipient= reallocate_emp,
                    verb=f"You have a new shift reallocation request from {instance.employee_id}.",
                    verb_ar=f"لديك طلب تخصيص جديد للورديات من {instance.employee_id}.",
                    verb_de=f"Sie haben eine neue Anfrage zur Verschiebung der Schichtzuteilung von {instance.employee_id}.",
                    verb_es=f"Tienes una nueva solicitud de reasignación de turnos de {instance.employee_id}.",
                    verb_fr=f"Vous avez une nouvelle demande de réaffectation de shift de {instance.employee_id}.",
                    icon="information",
                    redirect=f"/employee/shift-request-view?id={instance.id}",
                )
            except Exception as e:
                pass

            messages.success(request, _("Request Added"))
            return HttpResponse(response.content.decode("utf-8")+ "<script>location.reload();</script>")
    return render(
        request,
        "shift_request/htmx/shift_allocation_form.html",
        {"form": form, "f": f},
    )


@login_required
def shift_request_view(request):
    """
    This method renders all shift request instances to a template
    """
    previous_data = request.GET.urlencode()
    employee = Employee.objects.filter(employee_user_id=request.user).first()
    shift_requests = filtersubordinates(
        request, ShiftRequest.objects.filter(reallocate_to__isnull=True), "base.add_shiftrequest"
    )
    shift_requests = shift_requests | ShiftRequest.objects.filter(employee_id=employee)
    shift_requests = shift_requests.filter(employee_id__is_active=True)

    allocated_shift_requests = filtersubordinates(
        request, ShiftRequest.objects.filter(reallocate_to__isnull=False), "base.add_shiftrequest"
    )
    allocated_requests = ShiftRequest.objects.filter(reallocate_to__isnull=False)
    if not request.user.has_perm("base.view_shiftrequest"):
        allocated_requests = allocated_requests.filter(Q(reallocate_to=employee) | Q(employee_id=employee))
    allocated_shift_requests = allocated_shift_requests | allocated_requests

    requests_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                shift_requests, request.GET.get("page")
            ).object_list
        ]
    )
    allocated_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                allocated_shift_requests, request.GET.get("page")
            ).object_list
        ]
    )
    f = ShiftRequestFilter(request.GET, queryset=shift_requests)
    data_dict = parse_qs(previous_data)
    get_key_instances(ShiftRequest, data_dict)
    form = ShiftRequestForm()
    export_fields = ShiftRequestColumnForm()
    export_filter = ShiftRequestFilter()
    form = choosesubordinates(
        request,
        form,
        "base.add_shiftrequest",
    )
    form = include_employee_instance(request, form)
    return render(
        request,
        "shift_request/shift_request_view.html",
        {
            "allocated_data": paginator_qry(allocated_shift_requests, request.GET.get("page")),
            "data": paginator_qry(f.qs, request.GET.get("page")),
            "f": f,
            "form": form,
            "filter_dict": data_dict,
            "export_fields": export_fields,
            "export_filter": export_filter,
            "requests_ids": requests_ids,
            "allocated_ids": allocated_ids,
            "gp_fields": ShiftRequestReGroup.fields,
        },
    )

@login_required
@manager_can_enter("base.view_shiftrequest")
def shift_request_export(request):
    return export_data(
        request,
        ShiftRequest,
        ShiftRequestColumnForm,
        ShiftRequestFilter,
        "Shift_requests",
    )


@login_required
def shift_request_search(request):
    """
    This method is used search shift request by employee and also used to filter shift request.
    """

    employee = Employee.objects.filter(employee_user_id=request.user).first()
    previous_data = request.GET.urlencode()
    field = request.GET.get("field")
    f = ShiftRequestFilter(request.GET)
    f = sortby(request, f.qs, "sortby")
    shift_requests = filtersubordinates(request,f.filter(reallocate_to__isnull=True), "base.add_shiftrequest")
    shift_requests = shift_requests| f.filter(employee_id__employee_user_id=request.user)

    allocated_shift_requests = filtersubordinates(request,f.filter(reallocate_to__isnull=False), "base.add_shiftrequest")
    if not request.user.has_perm("base.view_shiftrequest"):
        allocated_shift_requests = allocated_shift_requests |f.filter(Q(reallocate_to=employee) | Q(employee_id=employee))

    requests_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                shift_requests, request.GET.get("page")
            ).object_list
        ]
    )

    allocated_ids = json.dumps(
        [
            instance.id
            for instance in paginator_qry(
                allocated_shift_requests, request.GET.get("page")
            ).object_list
        ]
    )

    data_dict = parse_qs(previous_data)
    template = "shift_request/htmx/requests.html"
    if field != "" and field is not None:
        field_copy = field.replace(".", "__")
        shift_requests = shift_requests.order_by(f"-{field_copy}")
        allocated_shift_requests = allocated_shift_requests.order_by(f"-{field_copy}")
        template = "shift_request/htmx/group_by.html"


    get_key_instances(ShiftRequest, data_dict)
    return render(
        request,
        template,
        {
            "allocated_data": paginator_qry(allocated_shift_requests, request.GET.get("page")),
            "data": paginator_qry(shift_requests, request.GET.get("page")),
            "pd": previous_data,
            "filter_dict": data_dict,
            "requests_ids": requests_ids,
            "allocated_ids":allocated_ids,
            "field": field,
        },
    )


@login_required
def shift_request_details(request, id):
    """
    This method is used to show shift request details in a modal
    args:
        id : shift request instance id
    """
    shift_request = ShiftRequest.objects.get(id=id)
    requests_ids_json = request.GET.get("instances_ids")
    context = {
        "shift_request": shift_request,
        "dashboard": request.GET.get("dashboard"),
    }
    if requests_ids_json:
        requests_ids = json.loads(requests_ids_json)
        previous_id, next_id = closest_numbers(requests_ids, id)
        context["previous"] = previous_id
        context["next"] = next_id
        context["requests_ids"] = requests_ids_json
    return render(
        request,
        "shift_request/htmx/shift_request_detail.html",
        context,
    )


@login_required
def shift_allocation_request_details(request, id):
    """
    This method is used to show shift request details in a modal
    args:
        id : shift request instance id
    """
    shift_request = ShiftRequest.objects.get(id=id)
    requests_ids_json = request.GET.get("instances_ids")
    context = {
        "shift_request": shift_request,
        "dashboard": request.GET.get("dashboard"),
    }
    if requests_ids_json:
        requests_ids = json.loads(requests_ids_json)
        previous_id, next_id = closest_numbers(requests_ids, id)
        context["previous"] = previous_id
        context["next"] = next_id
        context["allocation_ids"] = requests_ids_json
    return render(
        request,
        "shift_request/htmx/allocation_details.html",
        context,
    )



@login_required
@shift_request_change_permission()
def shift_request_update(request, shift_request_id):
    """
    This method is used to update shift request instance
    args:
        id : shift request instance id
    """
    shift_request = ShiftRequest.objects.get(id=shift_request_id)
    form = ShiftRequestForm(instance=shift_request)
    form = choosesubordinates(request, form, "base.change_shiftrequest")
    form = include_employee_instance(request, form)
    if request.method == "POST":
        response = render(
            request,
            "shift_request/request_update_form.html",
            {
                "form": form,
            },
        )
        form = ShiftRequestForm(request.POST, instance=shift_request)
        form = choosesubordinates(request, form, "base.change_shiftrequest")
        form = include_employee_instance(request, form)
        if form.is_valid():
            form.save()
            messages.success(request, _("Request Updated Successfully"))
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )

    return render(request, "shift_request/request_update_form.html", {"form": form})


@login_required
def shift_allocation_request_update(request, shift_request_id):
    """
    This method is used to update shift request instance
    args:
        id : shift request instance id
    """
    shift_request = ShiftRequest.objects.get(id=shift_request_id)
    form = ShiftAllocationForm(instance=shift_request)
    form = choosesubordinates(request, form, "base.change_shiftrequest")
    form = include_employee_instance(request, form)
    if request.method == "POST":
        response = render(
            request,
            "shift_request/request_update_form.html",
            {
                "form": form,
            },
        )
        form = ShiftAllocationForm(request.POST, instance=shift_request)
        form = choosesubordinates(request, form, "base.change_shiftrequest")
        form = include_employee_instance(request, form)
        if form.is_valid():
            form.save()
            instance = form.save()
            reallocate_emp = form.cleaned_data['reallocate_to']
            try:
                notify.send(
                    instance.employee_id,
                    recipient=(
                        instance.employee_id.employee_work_info.reporting_manager_id.employee_user_id
                    ),
                    verb=f"You have a new shift reallocation request to approve for {instance.employee_id}.",
                    verb_ar=f"لديك طلب تخصيص جديد للورديات يتعين عليك الموافقة عليه لـ {instance.employee_id}.",
                    verb_de=f"Sie haben eine neue Anfrage zur Verschiebung der Schichtzuteilung zur Genehmigung für {instance.employee_id}.",
                    verb_es=f"Tienes una nueva solicitud de reasignación de turnos para aprobar para {instance.employee_id}.",
                    verb_fr=f"Vous avez une nouvelle demande de réaffectation de shift à approuver pour {instance.employee_id}.",
                    icon="information",
                    redirect=f"/employee/shift-request-view?id={instance.id}",
                )
            except Exception as e:
                pass

            try:
                notify.send(
                    instance.employee_id,
                    recipient= reallocate_emp,
                    verb=f"You have a new shift reallocation request from {instance.employee_id}.",
                    verb_ar=f"لديك طلب تخصيص جديد للورديات من {instance.employee_id}.",
                    verb_de=f"Sie haben eine neue Anfrage zur Verschiebung der Schichtzuteilung von {instance.employee_id}.",
                    verb_es=f"Tienes una nueva solicitud de reasignación de turnos de {instance.employee_id}.",
                    verb_fr=f"Vous avez une nouvelle demande de réaffectation de shift de {instance.employee_id}.",
                    icon="information",
                    redirect=f"/employee/shift-request-view?id={instance.id}",
                )
            except Exception as e:
                pass
            messages.success(request, _("Request Updated Successfully"))
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )

    return render(request, "shift_request/allocation_request_update_form.html", {"form": form})


@login_required
def shift_request_cancel(request, id):
    """
    This method is used to update or cancel shift request
    args:
        id : shift request id

    """

    shift_request = ShiftRequest.objects.get(id=id)
    if (
        is_reportingmanger(request, shift_request)
        or request.user.has_perm("base.cancel_shiftrequest")
        or shift_request.employee_id == request.user.employee_get
        and shift_request.approved == False
    ):
        shift_request.canceled = True
        shift_request.approved = False
        shift_request.employee_id.employee_work_info.shift_id = (
            shift_request.previous_shift_id
        )

        if shift_request.reallocate_to:
            shift_request.reallocate_to.employee_work_info.shift_id = shift_request.shift_id
            shift_request.reallocate_to.employee_work_info.save()

        shift_request.employee_id.employee_work_info.save()
        shift_request.save()
        messages.success(request, _("Shift request rejected"))
        notify.send(
            request.user.employee_get,
            recipient=shift_request.employee_id.employee_user_id,
            verb="Your shift request has been canceled.",
            verb_ar="تم إلغاء طلبك للوردية.",
            verb_de="Ihr Schichtantrag wurde storniert.",
            verb_es="Se ha cancelado su solicitud de turno.",
            verb_fr="Votre demande de quart a été annulée.",
            redirect=f"/employee/shift-request-view?id={shift_request.id}",
            icon="close",
        )
        if shift_request.reallocate_to:
            notify.send(
                request.user.employee_get,
                recipient=shift_request.reallocate_to.employee_user_id,
                verb="Your shift request has been rejected.",
                verb_ar="تم إلغاء طلبك للوردية.",
                verb_de="Ihr Schichtantrag wurde storniert.",
                verb_es="Se ha cancelado su solicitud de turno.",
                verb_fr="Votre demande de quart a été annulée.",
                redirect=f"/employee/shift-request-view?id={shift_request.id}",
                icon="close",
            )

        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
    return HttpResponse("You cant cancel the request")


@login_required
def shift_allocation_request_cancel(request, id):
    """
    This method is used to update or cancel shift request
    args:
        id : shift request id

    """

    shift_request = ShiftRequest.objects.get(id=id)

    shift_request.reallocate_canceled = True
    shift_request.reallocate_approved = False
    shift_request.employee_id.employee_work_info.shift_id = (
        shift_request.previous_shift_id
    )
    shift_request.employee_id.employee_work_info.save()
    shift_request.save()
    messages.success(request, _("Shift request canceled"))
    notify.send(
        request.user.employee_get,
        recipient=shift_request.employee_id.employee_user_id,
        verb="Your shift request has been canceled.",
        verb_ar="تم إلغاء طلبك للوردية.",
        verb_de="Ihr Schichtantrag wurde storniert.",
        verb_es="Se ha cancelado su solicitud de turno.",
        verb_fr="Votre demande de quart a été annulée.",
        redirect=f"/employee/shift-request-view?id={shift_request.id}",
        icon="close",
    )

    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))



@login_required
@manager_can_enter("base.change_shiftrequest")
@require_http_methods(["POST"])
def shift_request_bulk_cancel(request):
    """
    This method is used to cancel a bunch of shift request.
    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    result = False
    for id in ids:
        shift_request = ShiftRequest.objects.get(id=id)
        if (
            is_reportingmanger(request, shift_request)
            or request.user.has_perm("base.cancel_shiftrequest")
            or shift_request.employee_id == request.user.employee_get
            and shift_request.approved == False
        ):
            shift_request.canceled = True
            shift_request.approved = False
            shift_request.employee_id.employee_work_info.shift_id = (
                shift_request.previous_shift_id
            )

            if shift_request.reallocate_to:
                shift_request.reallocate_to.employee_work_info.shift_id = shift_request.shift_id
                shift_request.reallocate_to.employee_work_info.save()

            shift_request.employee_id.employee_work_info.save()
            shift_request.save()
            messages.success(request, _("Shift request canceled"))
            notify.send(
                request.user.employee_get,
                recipient=shift_request.employee_id.employee_user_id,
                verb="Your shift request has been canceled.",
                verb_ar="تم إلغاء طلبك للوردية.",
                verb_de="Ihr Schichtantrag wurde storniert.",
                verb_es="Se ha cancelado su solicitud de turno.",
                verb_fr="Votre demande de quart a été annulée.",
                redirect=f"/employee/shift-request-view?id={shift_request.id}",
                icon="close",
            )
            if shift_request.reallocate_to:
                notify.send(
                    request.user.employee_get,
                    recipient=shift_request.employee_id.employee_user_id,
                    verb="Your shift request has been canceled.",
                    verb_ar="تم إلغاء طلبك للوردية.",
                    verb_de="Ihr Schichtantrag wurde storniert.",
                    verb_es="Se ha cancelado su solicitud de turno.",
                    verb_fr="Votre demande de quart a été annulée.",
                    redirect=f"/employee/shift-request-view?id={shift_request.id}",
                    icon="close",
                )
            result = True
    return JsonResponse({"result": result})


@login_required
@manager_can_enter("base.change_shiftrequest")
def shift_request_approve(request, id):
    """
    This method is used to approve shift request
    args:
        id : shift request instance id
    """

    shift_request = ShiftRequest.objects.get(id=id)

    if (
        is_reportingmanger(request, shift_request)
        or request.user.has_perm("approve_shiftrequest")
        or request.user.has_perm("change_shiftrequest")
        and not shift_request.approved
    ):
        """
        here the request will be approved, can send mail right here
        """

        if not shift_request.is_any_request_exists():
            shift_request.approved = True
            shift_request.canceled = False

            if shift_request.reallocate_to:
                shift_request.reallocate_to.employee_work_info.shift_id = shift_request.previous_shift_id
                shift_request.reallocate_to.employee_work_info.save()

            shift_request.save()
            messages.success(request, _("Shift has been approved."))
            notify.send(
                request.user.employee_get,
                recipient=shift_request.employee_id.employee_user_id,
                verb="Your shift request has been approved.",
                verb_ar="تمت الموافقة على طلبك للوردية.",
                verb_de="Ihr Schichtantrag wurde genehmigt.",
                verb_es="Se ha aprobado su solicitud de turno.",
                verb_fr="Votre demande de quart a été approuvée.",
                redirect=f"/employee/shift-request-view?id={shift_request.id}",
                icon="checkmark",
            )
            if shift_request.reallocate_to:
                notify.send(
                    request.user.employee_get,
                    recipient=shift_request.reallocate_to.employee_user_id,
                    verb="Your shift request has been approved.",
                    verb_ar="تمت الموافقة على طلبك للوردية.",
                    verb_de="Ihr Schichtantrag wurde genehmigt.",
                    verb_es="Se ha aprobado su solicitud de turno.",
                    verb_fr="Votre demande de quart a été approuvée.",
                    redirect=f"/employee/shift-request-view?id={shift_request.id}",
                    icon="checkmark",
                )
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
        else:
            messages.error(
                request, _("A shift request already exists during this time period.")
            )
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
    return HttpResponse("You Dont Have Permission")



@login_required
def shift_allocation_request_approve(request, id):
    """
    This method is used to approve shift request
    args:
        id : shift request instance id
    """

    shift_request = ShiftRequest.objects.get(id=id)

    if not shift_request.is_any_request_exists():
        shift_request.reallocate_approved = True
        shift_request.reallocate_canceled = False
        shift_request.save()
        messages.success(request, _("You are available for shift reallocation."))
        notify.send(
            request.user.employee_get,
            recipient=shift_request.employee_id.employee_user_id,
            verb=f"{request.user.employee_get} is available for shift reallocation.",
            verb_ar=f"{request.user.employee_get} متاح لإعادة توزيع الورديات.",
            verb_de=f"{request.user.employee_get} steht für die Verschiebung der Schichtzuteilung zur Verfügung.",
            verb_es=f"{request.user.employee_get} está disponible para la reasignación de turnos.",
            verb_fr=f"{request.user.employee_get} est disponible pour la réaffectation de shift.",
            redirect=f"/employee/shift-request-view?id={shift_request.id}",
            icon="checkmark",
        )
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
    else:
        messages.error(
            request, _("A shift request already exists during this time period.")
        )
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@require_http_methods(["POST"])
@manager_can_enter("base.change_shiftrequest")
def shift_request_bulk_approve(request):
    """
    This method is used to approve a bunch of shift request
    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    result = False
    for id in ids:
        shift_request = ShiftRequest.objects.get(id=id)
        if (
            is_reportingmanger(request, shift_request)
            or request.user.has_perm("approve_shiftrequest")
            or request.user.has_perm("change_shiftrequest")
            and not shift_request.approved
        ):
            """
            here the request will be approved, can send mail right here
            """
            shift_request.approved = True
            shift_request.canceled = False

            if shift_request.reallocate_to:
                shift_request.reallocate_to.employee_work_info.shift_id = shift_request.previous_shift_id
                shift_request.reallocate_to.employee_work_info.save()

            employee_work_info = shift_request.employee_id.employee_work_info
            employee_work_info.shift_id = shift_request.shift_id
            employee_work_info.save()
            shift_request.save()
            messages.success(request, _("Shifts have been approved."))
            notify.send(
                request.user.employee_get,
                recipient=shift_request.employee_id.employee_user_id,
                verb="Your shift request has been approved.",
                verb_ar="تمت الموافقة على طلبك للوردية.",
                verb_de="Ihr Schichtantrag wurde genehmigt.",
                verb_es="Se ha aprobado su solicitud de turno.",
                verb_fr="Votre demande de quart a été approuvée.",
                redirect=f"/employee/shift-request-view?id={shift_request.id}",
                icon="checkmark",
            )
        result = True
    return JsonResponse({"result": result})


@login_required
@require_http_methods(["POST"])
def shift_request_delete(request, id):
    """
    This method is used to delete shift request instance
    args:
        id : shift request instance id

    """
    try:
        shift_request = ShiftRequest.objects.get(id=id)
        user = shift_request.employee_id.employee_user_id
        messages.success(request, "Shift request deleted")
        shift_request.delete()
        notify.send(
            request.user.employee_get,
            recipient=user,
            verb="Your shift request has been deleted.",
            verb_ar="تم حذف طلب الوردية الخاص بك.",
            verb_de="Ihr Schichtantrag wurde gelöscht.",
            verb_es="Se ha eliminado su solicitud de turno.",
            verb_fr="Votre demande de quart a été supprimée.",
            redirect="#",
            icon="trash",
        )

    except ShiftRequest.DoesNotExist:
        messages.error(request, _("Shift request not found."))
    except ProtectedError:
        messages.error(request, _("You cannot delete this shift request."))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@permission_required("delete_shiftrequest")
@require_http_methods(["POST"])
def shift_request_bulk_delete(request):
    """
    This method is used to delete shift request instance
    args:
        id : shift request instance id

    """
    ids = request.POST["ids"]
    ids = json.loads(ids)
    result = False
    for id in ids:
        try:
            shift_request = ShiftRequest.objects.get(id=id)
            user = shift_request.employee_id.employee_user_id
            shift_request.delete()
            messages.success(request, _("Shift request deleted."))
            notify.send(
                request.user.employee_get,
                recipient=user,
                verb="Your shift request has been deleted.",
                verb_ar="تم حذف طلب الوردية الخاص بك.",
                verb_de="Ihr Schichtantrag wurde gelöscht.",
                verb_es="Se ha eliminado su solicitud de turno.",
                verb_fr="Votre demande de quart a été supprimée.",
                redirect="#",
                icon="trash",
            )
        except ShiftRequest.DoesNotExist:
            messages.error(request, _("Shift request not found."))
        except ProtectedError:
            messages.error(
                request,
                _(
                    "You cannot delete {employee} shift request for the date {date}."
                ).format(
                    employee=shift_request.employee_id,
                    date=shift_request.requested_date,
                ),
            )
        result = True
    return JsonResponse({"result": result})


@login_required
def notifications(request):
    """
    This method will render notification items
    """
    all_notifications = request.user.notifications.unread()
    return render(
        request,
        "notification/notification_items.html",
        {"notifications": all_notifications},
    )


@login_required
def clear_notification(request):
    """
    This method is used to clear notification
    """
    try:
        request.user.notifications.read().delete()
        messages.success(request, _("Unread notifications removed."))
    except Exception as e:
        messages.error(request, e)
    notifications = request.user.notifications.unread()
    return render(
        request,
        "notification/notification_items.html",
        {"notifications": notifications},
    )


@login_required
def delete_all_notifications(request):
    try:
        request.user.notifications.read().delete()
        request.user.notifications.unread().delete()
        messages.success(request, _("All notifications removed."))
    except Exception as e:
        messages.error(request, e)
    notifications = request.user.notifications.all()
    return render(
        request, "notification/all_notifications.html", {"notifications": notifications}
    )


@login_required
def delete_notification(request, id):
    """
    This method is used to delete notification
    """
    try:
        request.user.notifications.get(id=id).delete()
        messages.success(request, _("Notification deleted."))
    except Exception as e:
        messages.error(request, e)
    notifications = request.user.notifications.all()
    return render(
        request, "notification/all_notifications.html", {"notifications": notifications}
    )


@login_required
def mark_as_read_notification(request, notification_id):
    notification = Notification.objects.get(id=notification_id)
    notification.mark_as_read()
    return redirect(notifications)


@login_required
def mark_as_read_notification_json(request):
    try:
        notification_id = request.POST["notification_id"]
        notification_id = int(notification_id)
        notification = Notification.objects.get(id=notification_id)
        notification.mark_as_read()
        return JsonResponse({"success": True})
    except:
        return JsonResponse({"success": False, "error": "Invalid request"})


@login_required
def read_notifications(request):
    """
    This method is to mark as read the notification
    """
    try:
        request.user.notifications.all().mark_all_as_read()
        messages.info(request, _("Notifications marked as read"))
    except Exception as e:
        messages.error(request, e)
    notifications = request.user.notifications.unread()

    return render(
        request,
        "notification/notification_items.html",
        {"notifications": notifications},
    )


@login_required
def all_notifications(request):
    """
    This method to render all notifications to template
    """
    return render(
        request,
        "notification/all_notifications.html",
        {"notifications": request.user.notifications.all()},
    )


@login_required
@permission_required("payroll.view_payrollsettings")
def settings(request):
    """
    This method is used to render settings template
    """
    instance = PayrollSettings.objects.first()
    form = PayrollSettingsForm(instance=instance)
    if request.method == "POST":
        form = PayrollSettingsForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _("Payroll settings updated."))
    return render(request, "payroll/settings/payroll_settings.html", {"form": form})


@login_required
def general_settings(request):
    """
    This method is used to render settings template
    """
    instance = AnnouncementExpire.objects.first()
    form = AnnouncementExpireForm(instance=instance)
    encashment_instance = EncashmentGeneralSettings.objects.first()
    encashment_form = EncashmentGeneralSettingsForm(instance=encashment_instance)
    history_tracking_instance = HistoryTrackingFields.objects.first()
    history_fields_form_initial = {}
    if history_tracking_instance:
        history_fields_form_initial = {
            "tracking_fields": history_tracking_instance.tracking_fields['tracking_fields']
        }
    history_fields_form = HistoryTrackingFieldsForm(initial = history_fields_form_initial)
    if request.method == "POST":
        form = AnnouncementExpireForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, _("Settings updated."))
            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
    return render(
        request,
        "base/general_settings.html",
        {
            "form": form,
            "encashment_form": encashment_form,
            "history_fields_form":history_fields_form,
        },
    )


@login_required
@permission_required("base.view_company")
def date_settings(request):
    """
    This method is used to render Date format selector in settings
    """
    return render(request, "base/company/date.html")


@permission_required("base.change_company")
@csrf_exempt  # Use this decorator if CSRF protection is enabled
def save_date_format(request):
    if request.method == "POST":
        # Taking the selected Date Format
        selected_format = request.POST.get("selected_format")

        if not len(selected_format):
            messages.error(request, _("Please select a valid date format."))
        else:
            user = request.user
            employee = user.employee_get

            # Taking the company_name of the user
            info = EmployeeWorkInformation.objects.filter(employee_id=employee)
            # Employee workinformation will not exists if he/she chnged the company, So can't save the date format.
            if info.exists():
                for data in info:
                    employee_company = data.company_id

                company_name = Company.objects.filter(company=employee_company)
                emp_company = company_name.first()

                # Save the selected format to the backend
                emp_company.date_format = selected_format
                emp_company.save()
                messages.success(request, _("Date format saved successfully."))
            else:
                messages.warning(
                    request, _("Date format cannot saved. You are not in the company.")
                )

            # Return a JSON response indicating success
            return JsonResponse({"success": True})

    # Return a JSON response for unsupported methods
    return JsonResponse({"error": False, "error": "Unsupported method"}, status=405)


@login_required
def get_date_format(request):
    user = request.user
    employee = user.employee_get

    # Taking the company_name of the user
    info = EmployeeWorkInformation.objects.filter(employee_id=employee)
    if info.exists():
        for data in info:
            employee_company = data.company_id
        company_name = Company.objects.filter(company=employee_company)
        emp_company = company_name.first()
        if emp_company:
            # Access the date_format attribute directly
            date_format = emp_company.date_format if emp_company else "MMM. D, YYYY"
        else:
            date_format = "MMM. D, YYYY"
    else:
        date_format = "MMM. D, YYYY"
    # Return the date format as JSON response
    return JsonResponse({"selected_format": date_format})


@permission_required("base.change_company")
@csrf_exempt  # Use this decorator if CSRF protection is enabled
def save_time_format(request):
    if request.method == "POST":
        # Taking the selected Time Format
        selected_format = request.POST.get("selected_format")

        if not len(selected_format):
            messages.error(request, _("Please select a valid time format."))
        else:
            user = request.user
            employee = user.employee_get

            # Taking the company_name of the user
            info = EmployeeWorkInformation.objects.filter(employee_id=employee)
            # Employee workinformation will not exists if he/she chnged the company, So can't save the time format.
            if info.exists():
                for data in info:
                    employee_company = data.company_id

                company_name = Company.objects.filter(company=employee_company)
                emp_company = company_name.first()

                # Save the selected format to the backend
                emp_company.time_format = selected_format
                emp_company.save()
                messages.success(request, _("Time format saved successfully."))
            else:
                messages.warning(
                    request, _("Time format cannot saved. You are not in the company.")
                )

            # Return a JSON response indicating success
            return JsonResponse({"success": True})

    # Return a JSON response for unsupported methods
    return JsonResponse({"error": False, "error": "Unsupported method"}, status=405)


@login_required
def get_time_format(request):
    user = request.user
    employee = user.employee_get

    # Taking the company_name of the user
    info = EmployeeWorkInformation.objects.filter(employee_id=employee)
    if info.exists():
        for data in info:
            employee_company = data.company_id
        company_name = Company.objects.filter(company=employee_company)
        emp_company = company_name.first()
        if emp_company:
            # Access the date_format attribute directly
            time_format = emp_company.time_format
        else:
            time_format = "hh:mm A"
    else:
        time_format = "hh:mm A"
    # Return the date format as JSON response
    return JsonResponse({"selected_format": time_format})

@login_required
def history_field_settings(request):
    if request.method == "POST":
        fields = request.POST.getlist("tracking_fields")
        history_object, created = HistoryTrackingFields.objects.get_or_create(
            pk=1, defaults={"tracking_fields": {"tracking_fields": fields}}
        )

        if not created:
            history_object.tracking_fields = {"tracking_fields": fields}
            history_object.save()

    return redirect(general_settings)


@login_required
@permission_required("attendance.view_attendancevalidationcondition")
def validation_condition_view(request):
    """
    This method view attendance validation conditions.
    """
    condition = AttendanceValidationCondition.objects.first()
    default_grace_time = GraceTime.objects.filter(is_default=True).first()
    return render(
        request,
        "attendance/break_point/condition.html",
        {"condition": condition, "default_grace_time": default_grace_time},
    )


@login_required
@permission_required("attendance.add_attendancevalidationcondition")
def validation_condition_create(request):
    """
    This method render a form to create attendance validation conditions,
    and create if the form is valid.
    """
    form = AttendanceValidationConditionForm()
    if request.method == "POST":
        form = AttendanceValidationConditionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Attendance Break-point settings created."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "attendance/break_point/condition_form.html",
        {"form": form},
    )


@login_required
@permission_required("attendance.change_attendancevalidationcondition")
def validation_condition_update(request, obj_id):
    """
    This method is used to update validation condition
    Args:
        obj_id : validation condition instance id
    """
    condition = AttendanceValidationCondition.objects.get(id=obj_id)
    form = AttendanceValidationConditionForm(instance=condition)
    if request.method == "POST":
        form = AttendanceValidationConditionForm(request.POST, instance=condition)
        if form.is_valid():
            form.save()
            messages.success(request, _("Attendance Break-point settings updated."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "attendance/break_point/condition_form.html",
        {"form": form, "condition": condition},
    )


@login_required
def shift_select(request):
    page_number = request.GET.get("page")

    if page_number == "all":
        if request.user.has_perm("base.view_shiftrequest"):
            employees = ShiftRequest.objects.all()
        else:
            employees = ShiftRequest.objects.filter(
                employee_id__employee_user_id=request.user
            ) | ShiftRequest.objects.filter(
                employee_id__employee_work_info__reporting_manager_id__employee_user_id=request.user
            )
        # employees = ShiftRequest.objects.all()

    employee_ids = [str(emp.id) for emp in employees]
    total_count = employees.count()

    context = {"employee_ids": employee_ids, "total_count": total_count}

    return JsonResponse(context, safe=False)


@login_required
def shift_select_filter(request):
    page_number = request.GET.get("page")
    filtered = request.GET.get("filter")
    filters = json.loads(filtered) if filtered else {}

    if page_number == "all":
        employee_filter = ShiftRequestFilter(
            filters, queryset=ShiftRequest.objects.all()
        )

        # Get the filtered queryset
        filtered_employees = employee_filter.qs

        employee_ids = [str(emp.id) for emp in filtered_employees]
        total_count = filtered_employees.count()

        context = {"employee_ids": employee_ids, "total_count": total_count}

        return JsonResponse(context)


@login_required
def work_type_select(request):
    page_number = request.GET.get("page")

    if page_number == "all":
        if request.user.has_perm("base.view_worktyperequest"):
            employees = WorkTypeRequest.objects.all()
        else:
            employees = WorkTypeRequest.objects.filter(
                employee_id__employee_user_id=request.user
            ) | WorkTypeRequest.objects.filter(
                employee_id__employee_work_info__reporting_manager_id__employee_user_id=request.user
            )

    employee_ids = [str(emp.id) for emp in employees]
    total_count = employees.count()

    context = {"employee_ids": employee_ids, "total_count": total_count}

    return JsonResponse(context, safe=False)


@login_required
def work_type_select_filter(request):
    page_number = request.GET.get("page")
    filtered = request.GET.get("filter")
    filters = json.loads(filtered) if filtered else {}

    if page_number == "all":
        employee_filter = WorkTypeRequestFilter(
            filters, queryset=WorkTypeRequest.objects.all()
        )

        # Get the filtered queryset
        filtered_employees = employee_filter.qs

        employee_ids = [str(emp.id) for emp in filtered_employees]
        total_count = filtered_employees.count()

        context = {"employee_ids": employee_ids, "total_count": total_count}

        return JsonResponse(context)


@login_required
def rotating_shift_select(request):
    page_number = request.GET.get("page")

    if page_number == "all":
        if request.user.has_perm("base.view_rotatingshiftassign"):
            employees = RotatingShiftAssign.objects.filter(is_active=True)
        else:
            employees = RotatingShiftAssign.objects.filter(
                employee_id__employee_work_info__reporting_manager_id__employee_user_id=request.user
            )
    else:
        employees = RotatingShiftAssign.objects.all()

    employee_ids = [str(emp.id) for emp in employees]
    total_count = employees.count()

    context = {"employee_ids": employee_ids, "total_count": total_count}

    return JsonResponse(context, safe=False)


@login_required
def rotating_shift_select_filter(request):
    page_number = request.GET.get("page")
    filtered = request.GET.get("filter")
    filters = json.loads(filtered) if filtered else {}

    if page_number == "all":
        employee_filter = RotatingShiftAssignFilters(
            filters, queryset=RotatingShiftAssign.objects.all()
        )

        # Get the filtered queryset
        filtered_employees = employee_filter.qs

        employee_ids = [str(emp.id) for emp in filtered_employees]
        total_count = filtered_employees.count()

        context = {"employee_ids": employee_ids, "total_count": total_count}

        return JsonResponse(context)


@login_required
def rotating_work_type_select(request):
    page_number = request.GET.get("page")

    if page_number == "all":
        if request.user.has_perm("base.view_rotatingworktypeassign"):
            employees = RotatingWorkTypeAssign.objects.filter(is_active=True)
        else:
            employees = RotatingWorkTypeAssign.objects.filter(
                employee_id__employee_work_info__reporting_manager_id__employee_user_id=request.user
            )
    else:
        employees = RotatingWorkTypeAssign.objects.all()

    employee_ids = [str(emp.id) for emp in employees]
    total_count = employees.count()

    context = {"employee_ids": employee_ids, "total_count": total_count}

    return JsonResponse(context, safe=False)


@login_required
def rotating_work_type_select_filter(request):
    page_number = request.GET.get("page")
    filtered = request.GET.get("filter")
    filters = json.loads(filtered) if filtered else {}

    if page_number == "all":
        employee_filter = RotatingWorkTypeAssignFilter(
            filters, queryset=RotatingWorkTypeAssign.objects.all()
        )

        # Get the filtered queryset
        filtered_employees = employee_filter.qs

        employee_ids = [str(emp.id) for emp in filtered_employees]
        total_count = filtered_employees.count()

        context = {"employee_ids": employee_ids, "total_count": total_count}

        return JsonResponse(context)


@login_required
def ticket_type_view(request):
    """
    This method is used to show Ticket type
    """
    ticket_types = TicketType.objects.all()
    return render(
        request, "base/ticket_type/ticket_type.html", {"ticket_types": ticket_types}
    )


@login_required
def ticket_type_create(request):
    """
    This method renders form and template to create Ticket type
    """
    form = TicketTypeForm()
    if request.method == "POST":
        form = TicketTypeForm(request.POST)
        if request.GET.get("ajax"):
            if form.is_valid():
                instance = form.save()
                response = {
                    "errors": "no_error",
                    "ticket_id": instance.id,
                    "title": instance.title,
                }
                return JsonResponse(response)

            errors = form.errors.as_json()
            return JsonResponse({"errors": errors})
        if form.is_valid():
            form.save()
            form = TicketTypeForm()
            messages.success(request, _("Ticket type has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/ticket_type/ticket_type_form.html",
        {
            "form": form,
        },
    )


@login_required
def ticket_type_update(request, t_type_id):
    """
    This method renders form and template to create Ticket type
    """
    ticket_type = TicketType.objects.get(id=t_type_id)
    form = TicketTypeForm(instance=ticket_type)
    if request.method == "POST":
        form = TicketTypeForm(request.POST, instance=ticket_type)
        if form.is_valid():
            form.save()
            form = TicketTypeForm()
            messages.success(request, _("Ticket type has been updated successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/ticket_type/ticket_type_form.html",
        {"form": form, "t_type_id": t_type_id},
    )


@login_required
def ticket_type_delete(request, t_type_id):
    TicketType.objects.get(id=t_type_id).delete()
    messages.success(request, _("Ticket type has been deleted successfully!"))
    return HttpResponse("<script>window.location.reload()</script>")


@login_required
def tag_view(request):
    """
    This method is used to show Ticket type
    """
    tags = Tags.objects.all()
    employeetags = EmployeeTag.objects.all()
    audittags = AuditTag.objects.all()
    return render(
        request,
        "base/tags/tags.html",
        {"tags": tags, "employeetags": employeetags, "audittags": audittags},
    )


@login_required
def tag_create(request):
    """
    This method renders form and template to create Ticket type
    """
    form = TagsForm()
    if request.method == "POST":
        form = TagsForm(request.POST)
        if form.is_valid():
            form.save()
            form = TagsForm()
            messages.success(request, _("Tag has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/tags/tags_form.html",
        {
            "form": form,
        },
    )


@login_required
def tag_update(request, tag_id):
    """
    This method renders form and template to create Ticket type
    """
    tag = Tags.objects.get(id=tag_id)
    form = TagsForm(instance=tag)
    if request.method == "POST":
        form = TagsForm(request.POST, instance=tag)
        if form.is_valid():
            form.save()
            form = TagsForm()
            messages.success(request, _("Tag has been updated successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/tags/tags_form.html",
        {"form": form, "tag_id": tag_id},
    )


@login_required
def tag_delete(request, tag_id):
    Tags.objects.get(id=tag_id).delete()
    messages.success(request, _("Tag has been deleted successfully!"))
    return redirect(tag_view)


@login_required
def employee_tag_create(request):
    """
    This method renders form and template to create Ticket type
    """
    form = EmployeeTagForm()
    if request.method == "POST":
        form = EmployeeTagForm(request.POST)
        if form.is_valid():
            form.save()
            form = EmployeeTagForm()
            messages.success(request, _("Tag has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/employee_tag/employee_tag_form.html",
        {
            "form": form,
        },
    )


@login_required
def employee_tag_update(request, tag_id):
    """
    This method renders form and template to create Ticket type
    """
    tag = EmployeeTag.objects.get(id=tag_id)
    form = EmployeeTagForm(instance=tag)
    if request.method == "POST":
        form = EmployeeTagForm(request.POST, instance=tag)
        if form.is_valid():
            form.save()
            form = EmployeeTagForm()
            messages.success(request, _("Tag has been updated successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/employee_tag/employee_tag_form.html",
        {"form": form, "tag_id": tag_id},
    )


@login_required
def employee_tag_delete(request, tag_id):
    EmployeeTag.objects.get(id=tag_id).delete()
    messages.success(request, _("Tag has been deleted successfully!"))
    return redirect(tag_view)


@login_required
def audit_tag_create(request):
    """
    This method renders form and template to create Ticket type
    """
    form = AuditTagForm()
    if request.method == "POST":
        form = AuditTagForm(request.POST)
        if form.is_valid():
            form.save()
            form = AuditTagForm()
            messages.success(request, _("Tag has been created successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/audit_tag/audit_tag_form.html",
        {
            "form": form,
        },
    )


@login_required
def audit_tag_update(request, tag_id):
    """
    This method renders form and template to create Ticket type
    """
    tag = AuditTag.objects.get(id=tag_id)
    form = AuditTagForm(instance=tag)
    if request.method == "POST":
        form = AuditTagForm(request.POST, instance=tag)
        if form.is_valid():
            form.save()
            form = AuditTagForm()
            messages.success(request, _("Tag has been updated successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/audit_tag/audit_tag_form.html",
        {"form": form, "tag_id": tag_id},
    )


@login_required
def audit_tag_delete(request, tag_id):
    AuditTag.objects.get(id=tag_id).delete()
    messages.success(request, _("Tag has been deleted successfully!"))
    return redirect(tag_view)


@login_required
def multiple_approval_condition(request):
    form = MultipleApproveConditionForm()
    conditions = MultipleApprovalCondition.objects.all().order_by("department")[::-1]
    create = True
    return render(
        request,
        "leave/leave_request/penalty/condition.html",
        {"form": form, "conditions": conditions, "create": create},
    )


@login_required
def multiple_level_approval_create(request):
    form = MultipleApproveConditionForm()
    create = True
    if request.method == "POST":
        form = MultipleApproveConditionForm(request.POST)
        dept_id = request.POST.get("department")
        condition_field = request.POST.get("condition_field")
        condition_operator = request.POST.get("condition_operator")
        condition_value = request.POST.get("condition_value")
        condition_start_value = request.POST.get("condition_start_value")
        condition_end_value = request.POST.get("condition_end_value")
        department = Department.objects.get(id=dept_id)
        instance = MultipleApprovalCondition()
        if form.is_valid():
            if condition_operator != "range":
                instance.department = department
                instance.condition_field = condition_field
                instance.condition_operator = condition_operator
                instance.condition_value = condition_value
            else:
                instance.department = department
                instance.condition_field = condition_field
                instance.condition_operator = condition_operator
                instance.condition_start_value = condition_start_value
                instance.condition_end_value = condition_end_value
            instance.save()
            sequence = 0
            for key, value in request.POST.items():
                if key.startswith("multi_approval_manager"):
                    if value:
                        sequence += 1
                        employee_id = int(value)
                        MultipleApprovalManagers.objects.create(
                            condition_id=instance,
                            sequence=sequence,
                            employee_id=employee_id,
                        )
            form = MultipleApproveConditionForm()
    conditions = MultipleApprovalCondition.objects.all().order_by("department")[::-1]
    return render(
        request,
        "leave/leave_request/penalty/create.html",
        {"form": form, "conditions": conditions, "create": create},
    )


def edit_approval_managers(form, managers):
    for i, manager in enumerate(managers):
        if i == 0:
            form.initial["multi_approval_manager"] = manager.employee_id
        else:
            field_name = f"multi_approval_manager_{i}"
            form.fields[field_name] = forms.ModelChoiceField(
                queryset=Employee.objects.all(),
                label=_("Approval Manager {}").format(i),
                widget=forms.Select(attrs={"class": "oh-select oh-select-2 mb-3"}),
                required=False,
            )
            form.initial[field_name] = manager.employee_id
    return form


def clear_form_fields_and_remove_extra_fields(form, managers):
    for i, _ in enumerate(managers, start=1):
        field_name = f"multi_approval_manager_{i}"
        if field_name in form.cleaned_data:
            del form.cleaned_data[field_name]
            form.fields.pop(field_name, None)


from django.db.models import F


def multiple_level_approval_edit(request, condition_id):
    create = False
    condition = MultipleApprovalCondition.objects.get(id=condition_id)
    managers = MultipleApprovalManagers.objects.filter(condition_id=condition).order_by(
        "sequence"
    )
    form = MultipleApproveConditionForm(instance=condition)
    edit_approval_managers(form, managers)
    if request.method == "POST":
        form = MultipleApproveConditionForm(request.POST, instance=condition)
        if form.is_valid():
            form.save()
            sequence = 0
            for key, value in request.POST.items():
                if key.startswith("multi_approval_manager"):
                    sequence += 1
                    if value:
                        employee_id = int(value)
                        instance = MultipleApprovalManagers.objects.filter(
                            condition_id=condition,
                            sequence=sequence,
                        )
                        if instance:
                            instance.update(employee_id=employee_id)
                        else:
                            MultipleApprovalManagers.objects.create(
                                condition_id=condition,
                                sequence=sequence,
                                employee_id=employee_id,
                            )
                    else:
                        MultipleApprovalManagers.objects.filter(
                            condition_id=condition, sequence=sequence
                        ).delete()
                        managers_sequence = MultipleApprovalManagers.objects.filter(
                            condition_id=condition, sequence__gt=sequence
                        ).order_by("sequence")

                        for upt_manager in managers_sequence:
                            upt_manager.sequence = F("sequence") - 1
                            upt_manager.save()
                        sequence -= 1
            return HttpResponse("<script>window.location.reload()</script>")

    conditions = MultipleApprovalCondition.objects.all().order_by("department")[::-1]
    return render(
        request,
        "leave/leave_request/penalty/create.html",
        {
            "form": form,
            "conditions": conditions,
            "create": create,
            "condition": condition,
        },
    )


@login_required
def multiple_level_approval_delete(request, condition_id):
    condition = MultipleApprovalCondition.objects.get(id=condition_id)
    condition.delete()
    return redirect(multiple_approval_condition)


@login_required
def create_shiftrequest_comment(request, shift_id):
    """
    This method renders form and template to create shift request comments
    """
    shift = ShiftRequest.objects.filter(id=shift_id).first()
    emp = request.user.employee_get
    form = ShiftrequestcommentForm(
        initial={"employee_id": emp.id, "request_id": shift_id}
    )

    if request.method == "POST":
        form = ShiftrequestcommentForm(request.POST)
        if form.is_valid():
            form.instance.employee_id = emp
            form.instance.request_id = shift
            form.save()
            form = ShiftrequestcommentForm(
                initial={"employee_id": emp.id, "request_id": shift_id}
            )
            messages.success(request, _("Comment added successfully!"))

            if request.user.employee_get.id == shift.employee_id.id:
                rec = (
                    shift.employee_id.employee_work_info.reporting_manager_id.employee_user_id
                )
                notify.send(
                    request.user.employee_get,
                    recipient=rec,
                    verb=f"{shift.employee_id}'s shift request has received a comment.",
                    verb_ar=f"تلقت طلب تحويل {shift.employee_id} تعليقًا.",
                    verb_de=f"{shift.employee_id}s Schichtantrag hat einen Kommentar erhalten.",
                    verb_es=f"La solicitud de turno de {shift.employee_id} ha recibido un comentario.",
                    verb_fr=f"La demande de changement de poste de {shift.employee_id} a reçu un commentaire.",
                    redirect=f"/employee/shift-request-view?id={shift.id}",
                    icon="chatbox-ellipses",
                )
            elif (
                request.user.employee_get.id
                == shift.employee_id.employee_work_info.reporting_manager_id.id
            ):
                rec = shift.employee_id.employee_user_id
                notify.send(
                    request.user.employee_get,
                    recipient=rec,
                    verb="Your shift request has received a comment.",
                    verb_ar="تلقت طلبك للتحول تعليقًا.",
                    verb_de="Ihr Schichtantrag hat einen Kommentar erhalten.",
                    verb_es="Tu solicitud de turno ha recibido un comentario.",
                    verb_fr="Votre demande de changement de poste a reçu un commentaire.",
                    redirect=f"/employee/shift-request-view?id={shift.id}",
                    icon="chatbox-ellipses",
                )
            else:
                rec = [
                    shift.employee_id.employee_user_id,
                    shift.employee_id.employee_work_info.reporting_manager_id.employee_user_id,
                ]
                notify.send(
                    request.user.employee_get,
                    recipient=rec,
                    verb=f"{shift.employee_id}'s shift request has received a comment.",
                    verb_ar=f"تلقت طلب تحويل {shift.employee_id} تعليقًا.",
                    verb_de=f"{shift.employee_id}s Schichtantrag hat einen Kommentar erhalten.",
                    verb_es=f"La solicitud de turno de {shift.employee_id} ha recibido un comentario.",
                    verb_fr=f"La demande de changement de poste de {shift.employee_id} a reçu un commentaire.",
                    redirect=f"/employee/shift-request-view?id={shift.id}",
                    icon="chatbox-ellipses",
                )
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "shift_request/htmx/shift_request_comment_form.html",
        {"form": form, "request_id": shift_id},
    )


@login_required
def view_shift_comment(request, shift_id):
    """
    This method is used to render all the notes of the employee
    """
    comments = ShiftrequestComment.objects.filter(request_id=shift_id)
    if request.FILES:
        files = request.FILES.getlist("files")
        comment_id = request.GET["comment_id"]
        comment = ShiftrequestComment.objects.get(id=comment_id)
        attachments = []
        for file in files:
            file_instance = BaserequestFile()
            file_instance.file = file
            file_instance.save()
            attachments.append(file_instance)
        comment.files.add(*attachments)
    return render(
        request,
        "shift_request/htmx/shift_comment.html",
        {
            "comments": comments,
            "request_id": shift_id,
        },
    )


@login_required
@permission_required("offboarding.delete_offboardingnote")
def delete_shift_comment_file(request):
    """
    Used to delete attachment
    """
    ids = request.GET.getlist("ids")
    BaserequestFile.objects.filter(id__in=ids).delete()
    shift_id = request.GET["shift_id"]
    comments = ShiftrequestComment.objects.filter(request_id=shift_id)
    return render(
        request,
        "shift_request/htmx/shift_comment.html",
        {
            "comments": comments,
            "request_id": shift_id,
        },
    )


@login_required
def view_work_type_comment(request, work_type_id):
    """
    This method is used to render all the notes of the employee
    """
    comments = WorktyperequestComment.objects.filter(request_id=work_type_id)
    if request.FILES:
        files = request.FILES.getlist("files")
        comment_id = request.GET["comment_id"]
        comment = WorktyperequestComment.objects.get(id=comment_id)
        attachments = []
        for file in files:
            file_instance = BaserequestFile()
            file_instance.file = file
            file_instance.save()
            attachments.append(file_instance)
        comment.files.add(*attachments)
    return render(
        request,
        "work_type_request/htmx/work_type_comment.html",
        {
            "comments": comments,
            "request_id": work_type_id,
        },
    )


@login_required
@permission_required("offboarding.delete_offboardingnote")
def delete_work_type_comment_file(request):
    """
    Used to delete attachment
    """
    ids = request.GET.getlist("ids")
    BaserequestFile.objects.filter(id__in=ids).delete()
    work_type_id = request.GET["work_type_id"]
    comments = WorktyperequestComment.objects.filter(request_id=work_type_id)
    return render(
        request,
        "work_type_request/htmx/work_type_comment.html",
        {
            "comments": comments,
            "request_id": work_type_id,
        },
    )


@login_required
def view_shiftrequest_comment(request, shift_id):
    """
    This method is used to show shift request comments
    """
    comments = ShiftrequestComment.objects.filter(request_id=shift_id).order_by(
        "-created_at"
    )
    no_comments = False
    if not comments.exists():
        no_comments = True

    return render(
        request,
        "shift_request/htmx/comment_view.html",
        {"comments": comments, "no_comments": no_comments},
    )


@login_required
def delete_shiftrequest_comment(request, comment_id):
    """
    This method is used to delete shift request comments
    """
    ShiftrequestComment.objects.get(id=comment_id).delete()

    messages.success(request, _("Comment deleted successfully!"))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def create_worktyperequest_comment(request, worktype_id):
    """
    This method renders form and template to create Work type request comments
    """
    work_type = WorkTypeRequest.objects.filter(id=worktype_id).first()
    emp = request.user.employee_get
    form = WorktyperequestcommentForm(
        initial={"employee_id": emp.id, "request_id": worktype_id}
    )

    if request.method == "POST":
        form = WorktyperequestcommentForm(request.POST)
        if form.is_valid():
            form.instance.employee_id = emp
            form.instance.request_id = work_type
            form.save()
            form = WorktyperequestcommentForm(
                initial={"employee_id": emp.id, "request_id": worktype_id}
            )
            messages.success(request, _("Comment added successfully!"))

            if request.user.employee_get.id == work_type.employee_id.id:
                rec = (
                    work_type.employee_id.employee_work_info.reporting_manager_id.employee_user_id
                )
                notify.send(
                    request.user.employee_get,
                    recipient=rec,
                    verb=f"{work_type.employee_id}'s work type request has received a comment.",
                    verb_ar=f"تلقت طلب نوع العمل {work_type.employee_id} تعليقًا.",
                    verb_de=f"{work_type.employee_id}s Arbeitsart-Antrag hat einen Kommentar erhalten.",
                    verb_es=f"La solicitud de tipo de trabajo de {work_type.employee_id} ha recibido un comentario.",
                    verb_fr=f"La demande de type de travail de {work_type.employee_id} a reçu un commentaire.",
                    redirect=f"/employee/work-type-request-view?id={work_type.id}",
                    icon="chatbox-ellipses",
                )
            elif (
                request.user.employee_get.id
                == work_type.employee_id.employee_work_info.reporting_manager_id.id
            ):
                rec = work_type.employee_id.employee_user_id
                notify.send(
                    request.user.employee_get,
                    recipient=rec,
                    verb="Your work type request has received a comment.",
                    verb_ar="تلقى طلب نوع العمل الخاص بك تعليقًا.",
                    verb_de="Ihr Arbeitsart-Antrag hat einen Kommentar erhalten.",
                    verb_es="Tu solicitud de tipo de trabajo ha recibido un comentario.",
                    verb_fr="Votre demande de type de travail a reçu un commentaire.",
                    redirect=f"/employee/work-type-request-view?id={work_type.id}",
                    icon="chatbox-ellipses",
                )
            else:
                rec = [
                    work_type.employee_id.employee_user_id,
                    work_type.employee_id.employee_work_info.reporting_manager_id.employee_user_id,
                ]
                notify.send(
                    request.user.employee_get,
                    recipient=rec,
                    verb=f"{work_type.employee_id}'s work type request has received a comment.",
                    verb_ar=f"تلقت طلب نوع العمل {work_type.employee_id} تعليقًا.",
                    verb_de=f"{work_type.employee_id}s Arbeitsart-Antrag hat einen Kommentar erhalten.",
                    verb_es=f"La solicitud de tipo de trabajo de {work_type.employee_id} ha recibido un comentario.",
                    verb_fr=f"La demande de type de travail de {work_type.employee_id} a reçu un commentaire.",
                    redirect=f"/employee/work-type-request-view?id={work_type.id}",
                    icon="chatbox-ellipses",
                )
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "work_type_request/htmx/worktype_request_comment_form.html",
        {"form": form, "request_id": worktype_id},
    )


@login_required
def view_worktyperequest_comment(request, worktype_id):
    """
    This method is used to show Work type request comments
    """
    comments = WorktyperequestComment.objects.filter(request_id=worktype_id).order_by(
        "-created_at"
    )
    no_comments = False
    if not comments.exists():
        no_comments = True

    return render(
        request,
        "work_type_request/htmx/comment_view.html",
        {"comments": comments, "no_comments": no_comments},
    )


@login_required
def delete_worktyperequest_comment(request, comment_id):
    """
    This method is used to delete Work type request comments
    """
    WorktyperequestComment.objects.get(id=comment_id).delete()

    messages.success(request, _("Comment deleted successfully!"))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def pagination_settings_view(request):
    if DynamicPagination.objects.filter(user_id=request.user).exists():
        pagination = DynamicPagination.objects.filter(user_id=request.user).first()
        form = DynamicPaginationForm(instance=pagination)
        if request.method == "POST":
            form = DynamicPaginationForm(request.POST, instance=pagination)
            if form.is_valid():
                form.save()
                messages.success(request, _("Default pagination updated."))
    else:
        form = DynamicPaginationForm()
        if request.method == "POST":
            form = DynamicPaginationForm(
                request.POST,
            )
            if form.is_valid():
                form.save()
                messages.success(request, _("Default pagination updated."))
    return render(
        request, "base/dynamic_pagination/pagination_settings.html", {"form": form}
    )


@login_required
def action_type_view(request):
    """
    This method is used to show Action Type
    """
    action_types = Actiontype.objects.all()
    return render(
        request, "base/action_type/action_type.html", {"action_types": action_types}
    )


@login_required
def action_type_create(request):
    """
    This method renders form and template to create Action Type
    """
    form = ActiontypeForm()
    dynamic = request.GET.get("dynamic")
    hx_vals = request.GET.get("data")
    if request.method == "POST":
        form = ActiontypeForm(request.POST)
        if form.is_valid():
            form.save()
            form = ActiontypeForm()
            messages.success(request, _("Action has been created successfully!"))
            if dynamic == "None":
                return HttpResponse("<script>window.location.reload()</script>")
            else:
                from django.urls import reverse

                url = reverse("create-actions")
                instance = Actiontype.objects.all().order_by("-id").first()
                mutable_get = request.GET.copy()
                mutable_get["action"] = str(instance.id)
                return redirect(f"{url}?{mutable_get.urlencode()}")

    return render(
        request,
        "base/action_type/action_type_form.html",
        {
            "form": form,
            "dynamic": dynamic,
            "hx_vals": hx_vals,
        },
    )


@login_required
def action_type_update(request, act_id):
    """
    This method renders form and template to update Action type
    """
    action = Actiontype.objects.get(id=act_id)
    form = ActiontypeForm(instance=action)
    if request.method == "POST":
        form = ActiontypeForm(request.POST, instance=action)
        if form.is_valid():
            form.save()
            form = ActiontypeForm()
            messages.success(request, _("Action has been updated successfully!"))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "base/action_type/action_type_form.html",
        {"form": form, "act_id": act_id},
    )


@login_required
def action_type_delete(request, act_id):
    """
    This method is used to delete the action type.
    """
    Actiontype.objects.filter(id=act_id).delete()
    messages.success(request, _("Action has been deleted successfully!"))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
