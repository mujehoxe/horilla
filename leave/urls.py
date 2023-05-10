from django.urls import path
from django import views
from . import views


urlpatterns = [
    path('type-creation', views.leave_type_creation, name='type-creation'),
    path('type-view', views.leave_type_view, name='type-view'),
    path('type-update/<int:id>', views.leave_type_update, name='type-update'),
    path('type-delete/<int:id>', views.leave_type_delete, name='type-delete'),
    path('type-filter', views.leave_type_filter, name="type-filter"),

    path('request-creation', views.leave_request_creation, name='request-creation'),
    path('request-view', views.leave_request_view, name='request-view'),
    path('request-approve/<int:id>', views.leave_request_approve ,name='request-approve'),
    path('request-cancel/<int:id>', views.leave_request_cancel, name='request-cancel'),
    path('request-update/<int:id>',views.leave_request_update, name='request-update'),
    path('request-delete/<int:id>', views.leave_request_delete, name='request-delete'),
    path('user-request/<int:id>', views.user_leave_request, name='user-request'),
    path('request-filter', views.leave_request_filter, name='request-filter'),

    path('assign', views.leave_assign, name='assign'),
    path('assign-one/<int:id>', views.leave_assign_one, name='assign-one'),
    path('assign-view', views.leave_assign_view, name='assign-view'),
    path('available-leave-update/<int:id>', views.available_leave_update, name='available-leave-update'),
    path('assign-delete/<int:id>', views.leave_assign_delete, name='assign-delete'),
    path('assign-filter', views.leave_assign_filter, name='assign-filter'),
   


    path('holiday-view', views.holiday_view, name='holiday-view'),
    path('holiday-creation', views.holiday_creation, name='holiday-creation'),
    path('holiday-update/<int:id>', views.holiday_update, name='holiday-update'),
    path('holiday-delete/<int:id>', views.holiday_delete, name='holiday-delete'),
    path('holiday-filter', views.holiday_filter, name="holiday-filter"),

    path('company-leave-creation', views.company_leave_creation, name='company-leave-creation'),
    path('company-leave-view', views.company_leave_view, name='company-leave-view'),
    path('company-leave-update/<int:id>', views.company_leave_update, name='company-leave-update'),
    path('company-leave-delete/<int:id>', views.company_leave_delete, name='company-leave-delete'),
    path('company-leave-filter', views.company_leave_filter, name="company-leave-filter"),
  
    
    path('user-leave', views.user_leave_view, name='user-leave'),
    path('user-leave-filter', views.user_leave_filter, name='user-leave-filter'),
    path('user-request-view', views.user_request_view, name='user-request-view'),
    path('user-request-update/<int:id>', views.user_request_update, name='user-request-update'),
    path('user-request-delete/<int:id>', views.user_request_delete, name='user-request-delete'),
    path('one-request-view/<int:id>', views.one_request_view, name='one-request-view'),
    path('user-request-filter', views.user_request_filter, name="user-request-filter"),
    path('user-request-one/<int:id>', views.user_request_one, name='user-request-one'),

    path('employee-leave', views.employee_leave, name='employee-leave'),
    path('overall-leave', views.overall_leave, name="overall-leave"),

   
   
]
