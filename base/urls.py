from django.urls import path
from base import views

urlpatterns = [
    
    path('', views.home,name='home-page'),
    
    path('login', views.login_user,name='login'),

    path('forgot-password', views.forgot_password,name='forgot-password'),

    path('reset-password/<uuid>/', views.reset_password,name='reset-password'),
    
    path('logout', views.logout_user,name='logout'),

    path('settings', views.common_settings,name='settings'),
    
    path('settings/user-group-create',views.user_group_create,name='user-group-create'),
    
    path('user-group-view',views.user_group_view,name='user-group-view'),

    path('settings/user-group-update/<int:id>/',views.user_group_update,name='user-group-update'),

    path('user-group-delete/<int:id>/',views.user_group_delete,name='user-group-delete'),

    path('group-permission-remove/<int:pid>/<int:gid>/',views.user_group_permission_remove,name='group-permission-remove'),

    path('user-group-assign-view',views.group_assign_view,name='user-group-assign-view'),

    path('settings/user-group-assign',views.group_assign,name='user-group-assign'),   

    path('group-remove-user/<int:uid>/<int:gid>/',views.group_remove_user,name='group-remove-user'),
    
    path('settings/employee-permission-assign',views.employee_permission_assign,name='employee-permission-assign'),
    
    path('employee-permission-search',views.employee_permission_search,name='permission-search'),
    
    path('remove-permission/<str:codename>/<int:uid>/',views.remove_permission,name='remove-permission'),
    
    path('settings/company-create', views.company_create,name='company-create'),
    
    # path('company-view', views.company_view,name='company-view'),
    
    path('settings/company-update/<int:id>/', views.company_update,name='company-update'),
    
    path('company-delete/<int:id>/', views.company_delete,name='company-delete'),
    
    path('settings/department-creation', views.department,name='department-creation'),
    
    
    path('settings/department-update/<int:id>/', views.department_update,name='department-update'),
    
    path('department-delete/<int:id>/', views.department_delete,name='department-delete'),
    
    path('settings/job-position-creation', views.job_position,name='job-position-creation'),
        
    path('settings/job-position-update/<int:id>/', views.job_position_update,name='job-position-update'),
    
    path('job-position-delete/<int:id>/', views.job_position_delete,name='job-position-delete'),
    
    path('settings/job-role-create',views.job_role_create,name='job-role-create'),
        
    path('settings/job-role-update/<int:id>/',views.job_role_update,name='job-role-update'),
    
    path('job-role-delete/<int:id>/',views.job_role_delete,name='job-role-delete'),                   
    
    path('settings/work-type-create', views.work_type_create,name='work-type-create'),
    
    path('settings/work-type-update/<int:id>/', views.work_type_update,name='work-type-update'),
    
    path('work-type-delete/<int:id>/', views.work_type_delete,name='work-type-delete'),
    
    path('settings/rotating-work-type-create',views.rotating_work_type_create,name='rotating-work-type-create'),
        
    path('settings/rotating-work-type-update/<int:id>/',views.rotating_work_type_update,name='rotating-work-type-update'),
    
    path('rotating-work-type-delete/<int:id>/',views.rotating_work_type_delete,name='rotating-work-type-delete'),
    
    path('employee/rotating-work-type-assign',views.rotating_work_type_assign,name='rotating-work-type-assign'),

    path('rotating-work-type-assign-add',views.rotating_work_type_assign_add,name="rotating-work-type-assign-add"),
    
    path('rotating-work-type-assign-view',views.rotating_work_type_assign_view,name='rotating-work-type-assign-view'),
    
    path('settings/rotating-work-type-assign-update/<int:id>/',views.rotating_work_type_assign_update,name='rotating-work-type-assign-update'),

    path('rotating-work-type-assign-archive/<int:id>/',views.rotating_work_type_assign_archive,name='rotating-work-type-assign-archive'),

    path('rotating-work-type-assign-bulk-archive',views.rotating_work_type_assign_bulk_archive,name='rotating-shift-work-type-bulk-archive'),

    path('rotating-work-type-assign-bulk-delete',views.rotating_work_type_assign_bulk_delete,name='rotating-shift-work-type-bulk-delete'),
    
    path('rotating-work-type-assign-delete/<int:id>/',views.rotating_work_type_assign_delete,name='rotating-work-type-assign-delete'),
    
    path('settings/employee-type-create', views.employee_type_create,name='employee-type-create'),
        
    path('settings/employee-type-update/<int:id>/', views.employee_type_update,name='employee-type-update'),
    
    path('employee-type-delete/<int:id>/', views.employee_type_delete,name='employee-type-delete'),
    
    path('settings/employee-shift-create', views.employee_shift_create,name='employee-shift-create'),
        
    path('settings/employee-shift-update/<int:id>/', views.employee_shift_update,name='employee-shift-update'),
    
    path('employee-shift-delete/<int:id>/', views.employee_shift_delete,name='employee-shift-delete'),
    
    path('settings/employee-shift-schedule-create', views.employee_shift_schedule_create,name='employee-shift-schedule-create'),
        
    path('settings/employee-shift-schedule-update/<int:id>/', views.employee_shift_schedule_update,name='employee-shift-schedule-update'),
    
    path('employee-shift-schedule-delete/<int:id>/', views.employee_shift_schedule_delete,name='employee-shift-schedule-delete'),
    
    path('settings/rotating-shift-create',views.rotating_shift_create,name='rotating-shift-create'),
        
    path('settings/rotating-shift-update/<int:id>/',views.rotating_shift_update,name='rotating-shift-update'),
    
    path('rotating-shift-delete/<int:id>/',views.rotating_shift_delete,name='rotating-shift-delete'),
    
    path('employee/rotating-shift-assign',views.rotating_shift_assign,name='rotating-shift-assign'),

    path('rotating-shift-assign-add',views.rotating_shift_assign_add,name='rotating-shift-assign-add'),
    
    path('rotating-shift-assign-view',views.rotating_shift_assign_view,name='rotating-shift-assign-view'),

    path('settings/rotating-shift-assign-update/<int:id>/',views.rotating_shift_assign_update,name='rotating-shift-assign-update'),

    path('rotating-shift-assign-archive/<int:id>/',views.rotating_shift_assign_archive,name='rotating-shift-assign-archive'),

    path('rotating-shift-assign-bulk-archive',views.rotating_shift_assign_bulk_archive,name='rotating-shift-assign-bulk-archive'),

    path('rotating-shift-assign-bulk-delete',views.rotating_shift_assign_bulk_delete,name='rotating-shift-assign-bulk-delete'),
    
    path('rotating-shift-assign-delete/<int:id>/',views.rotating_shift_assign_delete,name='rotating-shift-assign-delete'),
    
    path('work-type-request',views.work_type_request,name='work-type-request'),
    
    path('work-type-requests/work-type-request-view',views.work_type_request_view,name='work-type-request-view'),

    path('work-type-request-search',views.work_type_request_search,name='work-type-request-search'),

    path('work-type-request-cancel/<int:id>/',views.work_type_request_cancel,name='work-type-request-cancel'),

    path('work-type-request-bulk-cancel',views.work_type_request_bulk_cancel,name='work-type-request-bulk-cancel'),
    
    path('work-type-request-approve/<int:id>/',views.work_type_request_approve,name='work-type-request-approve'),

    path('work-type-request-bulk-approve',views.work_type_request_bulk_approve,name='work-type-request-bulk-approve'),
    
    path('work-type-request-update/<int:id>/',views.work_type_request_update,name='work-type-request-update'),
    
    path('work-type-request-delete/<int:id>/',views.work_type_request_delete,name='work-type-request-delete'),

    path('work-type-request-bulk-delete',views.work_type_request_bulk_delete,name="work-type-request-bulk-delete"),
    
    path('shift-request',views.shift_request,name='shift-request'),
    
    path('shift-requests/shift-request-view',views.shift_request_view,name='shift-request-view'),

    path('shift-request-search',views.shift_request_search,name='shift-request-search'),
    
    path('shift-request-update/<int:id>/',views.shift_request_update,name='shift-request-update'),
    
    path('shift-request-cancel/<int:id>/',views.shift_request_cancel,name='shift-request-cancel'),

    path('shift-request-bulk-cancel',views.shift_request_bulk_cancel,name="shift-request-bulk-cancel"),
    
    path('shift-request-approve/<int:id>/',views.shift_request_approve,name='shift-request-approve'),

    path('shift-request-bulk-approve',views.shift_request_bulk_approve,name="shift-request-bulk-approve"),
    
    path('shift-request-delete/<int:id>/',views.shift_request_delete,name='shift-request-delete'),

    path('shift-request-bulk-delete',views.shift_request_bulk_delete,name="shift-request-bulk-delete"),
    
    path('notifications',views.notifications,name="notifications"),

    path('clear-notifications',views.clear_notification,name="clear-notifications"),

    path('read-notifications',views.read_notifications,name="read-notifications"),

    path('all-notifications',views.all_notifications,name="all-notifications"),

    path('delete-notifications/<id>/',views.delete_notification,name="delete-notifications"),


    

]
