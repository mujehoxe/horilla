import django
from django.db import models
from simple_history.models import HistoricalRecords
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Create your models here.

def validate_time_format(value):
    '''
    this method is used to validate the format of duration like fields.
    '''
    if len(value) > 6:
        raise ValidationError(_("Invalid format, it should be HH:MM format"))
    try:
        hour, minute = value.split(":")
        hour = int(hour)
        minute = int(minute)
        if len(str(hour)) > 3 or minute not in range(60):
            raise ValidationError(_("Invalid time"))
    except ValueError as e:
        raise ValidationError(_("Invalid format")) from e



class Company(models.Model):
    company = models.CharField(max_length=50)
    hq = models.BooleanField(default=False)
    address = models.TextField()
    country = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    city = models.CharField(max_length=50)
    zip = models.CharField(max_length=20)
    icon = models.FileField(upload_to='base/icon',null=True,)
    class Meta:
        unique_together = ['company','address']

    def __str__(self) -> str:
        return self.company


class Department(models.Model):
    department = models.CharField(max_length=50, blank=False,unique=True)
    history = HistoricalRecords()

    def __str__(self):
        return self.department


class JobPosition(models.Model):
    job_position = models.CharField(max_length=50, blank=False, null=False, unique=True)
    department_id = models.ForeignKey(
        Department, on_delete=models.CASCADE, blank=True, related_name='job_position', verbose_name='Department')
    def __str__(self):
        return self.job_position


class JobRole(models.Model):
    job_position_id = models.ForeignKey(JobPosition, on_delete=models.CASCADE, verbose_name='Job Position')
    job_role = models.CharField(max_length=50,blank=False,null=True)
    class Meta:
        unique_together = ('job_position_id','job_role')
    def __str__(self):
        return f'{self.job_role} - {self.job_position_id.job_position}'

class WorkType(models.Model):
    work_type = models.CharField(max_length=50)
    def __str__(self) -> str:
        return self.work_type

class RotatingWorkType(models.Model):
    name = models.CharField(max_length=50)
    work_type1 = models.ForeignKey(WorkType,on_delete=models.CASCADE,related_name='work_type1',verbose_name=_('Work Type 1'))
    work_type2 = models.ForeignKey(WorkType,on_delete=models.CASCADE,related_name='work_type2',verbose_name=_('Work Type 2'))
    employee_id = models.ManyToManyField('employee.Employee', through='RotatingWorkTypeAssign',verbose_name="Employee")

    def __str__(self) -> str:
        return self.name
    
    def clean(self):
        if self.work_type1 == self.work_type2:
            raise ValidationError(_('Choose different work type'))


DAY_DATE = [(str(i), str(i)) for i in range(1, 32)]
DAY_DATE.append(('last', _('Last Day')))    
DAY = [    
    ('monday', _('Monday')),
    ('tuesday', _('Tuesday')),
    ('wednesday', _('Wednesday')),    
    ('thursday', _('Thursday')),    
    ('friday', _('Friday')),    
    ('saturday', _('Saturday')),    
    ('sunday', _('Sunday')),
]
BASED_ON = [
    ('after',_('After')),
    ('weekly',_('Weekend')),
    ('monthly',_('Monthly')),
]

class RotatingWorkTypeAssign(models.Model):
    
    employee_id = models.ForeignKey('employee.Employee',on_delete=models.CASCADE,null=True,verbose_name="Employee")
    rotating_work_type_id = models.ForeignKey(RotatingWorkType,on_delete=models.CASCADE,verbose_name='Rotating Work Type')
    next_change_date = models.DateField(null=True)
    start_date = models.DateField(default= django.utils.timezone.now)
    based_on = models.CharField(max_length=10,choices=BASED_ON,null=False,blank=False)
    rotate_after_day = models.IntegerField(default=7)
    rotate_every_weekend = models.CharField(max_length=10,default='monday',choices=DAY,blank=True,null=True)
    rotate_every = models.CharField(max_length=10,default='1',choices=DAY_DATE)
    current_work_type = models.ForeignKey(WorkType,null=True,on_delete=models.DO_NOTHING,related_name='current_work_type')
    next_work_type = models.ForeignKey(WorkType,null=True,on_delete=models.DO_NOTHING,related_name='next_work_type')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-next_change_date','-employee_id__employee_first_name']

    def clean(self):
        if self.is_active and self.employee_id is not None:
            # Check if any other active record with the same parent already exists
            siblings = RotatingWorkTypeAssign.objects.filter(is_active=True, employee_id=self.employee_id)
            if siblings.exists() and siblings.first().id != self.id:
                raise ValidationError(_('Only one active record allowed per employee'))
        if self.start_date < django.utils.timezone.now().date():
            raise ValidationError(_('Date must be greater than or equal to today'))


class EmployeeType(models.Model):
    employee_type = models.CharField(max_length=50)

    def __str__(self) -> str:
        return self.employee_type

class EmployeeShiftDay(models.Model):

    day = models.CharField(max_length=20, choices=DAY)
    def __str__(self) -> str:
        return self.day

class EmployeeShift(models.Model):
    employee_shift = models.CharField(max_length=50, null=False, blank=False,)
    days = models.ManyToManyField(
        EmployeeShiftDay, through='EmployeeShiftSchedule')
    weekly_full_time = models.CharField(max_length=6,default='40:00',null=True,blank=True)
    full_time = models.CharField(max_length=6,default='200:00',validators=[validate_time_format])


    def __str__(self) -> str:
        return self.employee_shift

class EmployeeShiftSchedule(models.Model):
    day = models.ForeignKey(EmployeeShiftDay,
                            on_delete=models.CASCADE,related_name='day_schedule')
    shift_id = models.ForeignKey(
        EmployeeShift, on_delete=models.CASCADE,verbose_name='Shift')
    minimum_working_hour = models.CharField(default='08:15',max_length=5,validators=[validate_time_format])
    start_time = models.TimeField(null=True)
    end_time = models.TimeField(null=True) 

    class Meta:
        unique_together = [
            ['shift_id', 'day']
        ]

    def __str__(self) -> str:
        return f'{self.shift_id.employee_shift} {self.day}'

class RotatingShift(models.Model):
    name =models.CharField(max_length=50)
    employee_id = models.ManyToManyField('employee.Employee',through='RotatingShiftAssign',verbose_name='Employee')
    shift1 = models.ForeignKey(EmployeeShift,related_name='shift1',on_delete=models.CASCADE,verbose_name=_('Shift 1'))
    shift2 = models.ForeignKey(EmployeeShift,related_name='shift2',on_delete=models.CASCADE,verbose_name=_('Shift 2'))

    def __str__(self) -> str:
        return self.name
    def clean(self):
        if self.shift1 == self.shift2:
            raise ValidationError(_('Choose different shifts'))


class RotatingShiftAssign(models.Model):

    # employee_id = models.OneToOneField('employee.Employee',on_delete=models.CASCADE)
    employee_id = models.ForeignKey('employee.Employee',on_delete=models.CASCADE,verbose_name='Employee')
    rotating_shift_id = models.ForeignKey(RotatingShift,on_delete=models.CASCADE,verbose_name='Rotating Shift')
    next_change_date = models.DateField(null=True)
    start_date = models.DateField(default=django.utils.timezone.now)
    based_on = models.CharField(max_length=10,choices=BASED_ON,null=False,blank=False)
    rotate_after_day = models.IntegerField(null=True,blank=True,default=7)
    rotate_every_weekend = models.CharField(max_length=10,default='monday',choices=DAY,blank=True,null=True)
    rotate_every = models.CharField(max_length=10,blank=True,null=True,default='1',choices=DAY_DATE)
    current_shift = models.ForeignKey(EmployeeShift,on_delete=models.DO_NOTHING,null=True,related_name='current_shift')
    next_shift = models.ForeignKey(EmployeeShift,on_delete=models.DO_NOTHING,null=True,related_name='next_shift')
    is_active=models.BooleanField(default=True)

    class Meta:
        ordering = ['-next_change_date','-employee_id__employee_first_name']
    
    def clean(self):
        if self.is_active and self.employee_id is not None:
            # Check if any other active record with the same parent already exists
            siblings = RotatingShiftAssign.objects.filter(is_active=True, employee_id=self.employee_id)
            if siblings.exists() and siblings.first().id != self.id:
                raise ValidationError(_('Only one active record allowed per employee'))
        if self.start_date < django.utils.timezone.now().date():
            raise ValidationError(_('Date must be greater than or equal to today'))


class WorkTypeRequest(models.Model):

    def save(self, *args, **kwargs):
        
        super(WorkTypeRequest,self).save(*args, **kwargs)

    employee_id = models.ForeignKey('employee.Employee',on_delete=models.CASCADE,null=True,related_name='work_type_request',verbose_name='Employee')
    requested_date = models.DateField(null=True,default=django.utils.timezone.now)
    requested_till = models.DateField(null=True,blank=True,default=django.utils.timezone.now)
    work_type_id = models.ForeignKey(WorkType,on_delete=models.CASCADE,related_name='requested_work_type',verbose_name='Work Type')
    previous_work_type_id = models.ForeignKey(WorkType,on_delete=models.DO_NOTHING,null=True,blank=True,related_name='previous_work_type')
    description = models.TextField(null=True)
    approved = models.BooleanField(default=False)
    canceled = models.BooleanField(default=False)
    work_type_changed = models.BooleanField(default=False)
    is_active= models.BooleanField(default=True)

    class Meta:
        permissions = (('approve_worktyperequest','Approve Work Type Request'),('cancel_worktyperequest','Cancel Work Type Request'))
        ordering = ['requested_date',]
        unique_together = ['employee_id','requested_date']
    
    def clean(self):
        if self.requested_date < django.utils.timezone.now().date():
            raise ValidationError(_('Date must be greater than or equal to today'))
        if self.requested_till and self.requested_till < self.requested_date:
            raise ValidationError(_('End date must be greater than or equal to start date'))


class ShiftRequest(models.Model):

    employee_id = models.ForeignKey('employee.Employee',on_delete=models.CASCADE,null=True,related_name='shift_request',verbose_name='Employee')
    requested_date = models.DateField(null=True,default=django.utils.timezone.now)
    requested_till = models.DateField(null=True,blank=True,default=django.utils.timezone.now)
    shift_id = models.ForeignKey(EmployeeShift,on_delete=models.CASCADE,related_name='requested_shift',verbose_name='Shift')    
    previous_shift_id = models.ForeignKey(EmployeeShift,on_delete=models.DO_NOTHING,null=True,blank=True,related_name='previous_shift')
    description = models.TextField(null=True)
    approved = models.BooleanField(default=False)
    canceled = models.BooleanField(default=False)
    shift_changed = models.BooleanField(default=False)
    is_active= models.BooleanField(default=True)

    class Meta:
        permissions = (('approve_shiftrequest','Approve Shift Request'),('cancel_shiftrequest','Cancel Shift Request'))
        ordering = ['requested_date',]
        unique_together = ['employee_id','requested_date']

    def clean(self):
        if self.requested_date < django.utils.timezone.now().date():
            raise ValidationError(_('Date must be greater than or equal to today'))
        if self.requested_till and self.requested_till < self.requested_date:
            raise ValidationError(_('End date must be greater than or equal to start date'))


    def save(self, *args, **kwargs):
        
        super(ShiftRequest,self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee_id}"