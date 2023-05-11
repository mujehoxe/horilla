from django.db import models
from base.models import EmployeeShift,EmployeeShiftDay, WorkType
from django.core.exceptions import ValidationError
from employee.models import Employee
from datetime import datetime
from django.utils.translation import gettext_lazy as _

# Create your models here. 


def strtime_seconds(time):
    '''
    this method is used reconvert time in H:M formate string back to seconds and return it
    args:
        time : time in H:M format
    '''
    ftr = [3600,60,1]
    return sum(a*b for a,b in zip(ftr, map(int,time.split(':'))))

def format_time(seconds):
    '''this method is used to formate seconds to H:M and return it
    args:
        seconds : seconds
    '''
    hour=int(seconds//3600)
    minutes=int((seconds%3600)//60)
    seconds=int((seconds%3600)%60)
    return "%02d:%02d" % (hour, minutes)


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

def attendance_date_validate(date):
    today = datetime.today().date()
    if date > today:
        raise ValidationError(_('You cannot choose future date'))
    



class AttendanceActivity(models.Model):
    employee_id = models.ForeignKey(Employee,on_delete=models.CASCADE, related_name='employee_attendance_activities')
    attendance_date = models.DateField(null=True, validators=[attendance_date_validate])
    clock_in_date=models.DateField(null=True)
    shift_day = models.ForeignKey(EmployeeShiftDay,null=True,on_delete=models.DO_NOTHING)
    clock_in = models.TimeField()
    clock_out = models.TimeField(null=True)
    clock_out_date = models.DateField(null=True)

    class Meta:
        ordering = ['-attendance_date','employee_id__employee_first_name','clock_in']



class Attendance(models.Model):
    employee_id = models.ForeignKey(
        Employee, on_delete=models.CASCADE, null=True, related_name='employee_attendances')
    shift_id = models.ForeignKey(
        EmployeeShift, on_delete=models.DO_NOTHING,null=True)
    work_type_id = models.ForeignKey(WorkType,null=True,blank=True,on_delete=models.DO_NOTHING)
    attendance_date = models.DateField(null=False,validators=[attendance_date_validate])
    attendance_day = models.ForeignKey(EmployeeShiftDay,on_delete=models.DO_NOTHING,null= True)
    attendance_clock_in = models.TimeField(null=True)
    attendance_clock_in_date = models.DateField(null=True)
    attendance_clock_out = models.TimeField(null=True, )
    attendance_clock_out_date = models.DateField(null=True)
    attendance_worked_hour = models.CharField(null=True,default='00:00',max_length=10,validators=[validate_time_format])
    minimum_hour = models.CharField(max_length = 10,default='00:00',validators=[validate_time_format])
    attendance_overtime = models.CharField(default='00:00',validators=[validate_time_format],max_length=10)
    attendance_overtime_approve = models.BooleanField(default=False)
    attendance_validated = models.BooleanField(default=False)
    at_work_second = models.IntegerField(null=True,blank=True)
    overtime_second = models.IntegerField(null=True, blank=True)
    approved_overtime_second = models.IntegerField(default=0)


    class Meta:
        unique_together= ('employee_id','attendance_date')
        permissions = [('change_validateattendance','Validate Attendance'),('change_approveovertime','Change Approve Overtime')]
        ordering = ['-attendance_date','employee_id__employee_first_name','attendance_clock_in']


    def __str__(self) -> str:
        return f'{self.employee_id.employee_first_name} {self.employee_id.employee_last_name} - {self.attendance_date}'

    def save(self, *args, **kwargs):
        self.at_work_second = strtime_seconds(self.attendance_worked_hour)
        self.overtime_second = strtime_seconds(self.attendance_overtime)
        self.attendance_day = EmployeeShiftDay.objects.get(day = self.attendance_date.strftime('%A').lower())
        prev_attendance_approved = False

        condition = AttendanceValidationCondition.objects.first()
        if condition is not None:
            overtime_cutoff = condition.overtime_cutoff
            cutoff_seconds = strtime_seconds(overtime_cutoff)
            overtime = self.overtime_second
            if overtime > cutoff_seconds:
                self.overtime_second = cutoff_seconds
            self.attendance_overtime = format_time(cutoff_seconds)
        
        if self.pk is not None:
            # Get the previous values of the boolean field
            prev_state = Attendance.objects.get(pk=self.pk)
            prev_attendance_approved = prev_state.attendance_overtime_approve

        super(Attendance, self).save(*args, **kwargs)
        employee_ot = self.employee_id.employee_overtime.filter(month=self.attendance_date.strftime('%B').lower(),year=self.attendance_date.strftime('%Y'))
        if employee_ot.exists():
            self.update_ot(employee_ot.first())
        else:
            self.create_ot()
        approved = self.attendance_overtime_approve
        attendance_account = self.employee_id.employee_overtime.filter(month=self.attendance_date.strftime('%B').lower(),year=self.attendance_date.year).first()
        total_ot_seconds = attendance_account.overtime_second
        if approved and prev_attendance_approved is False:
            self.approved_overtime_second = self.overtime_second
            total_ot_seconds = total_ot_seconds + self.approved_overtime_second
        elif not approved:
            total_ot_seconds = total_ot_seconds - self.approved_overtime_second
            self.approved_overtime_second = 0
        attendance_account.overtime = format_time(total_ot_seconds)
        attendance_account.save()
        super(Attendance, self).save(*args, **kwargs)
           

    def create_ot(self):
        '''
        this method is used to create new AttendanceOvertime's instance if there is no existing for a specific month and year
        '''
        employee_ot = AttendanceOverTime()
        employee_ot.employee_id = self.employee_id
        employee_ot.month = self.attendance_date.strftime('%B').lower()
        employee_ot.year = self.attendance_date.year
        if self.attendance_overtime_approve:
            employee_ot.overtime = self.attendance_overtime
        if self.attendance_validated:
            employee_ot.hour_account = self.attendance_worked_hour
        employee_ot.save()
        return

    def update_ot(self, employee_ot):
        month_attendances = Attendance.objects.filter(employee_id = self.employee_id, attendance_date__month=self.attendance_date.month,attendance_date__year=self.attendance_date.year,attendance_validated=True)
        hour_balance = 0
        for attendance in month_attendances:
            hour_balance = hour_balance + attendance.at_work_second
        employee_ot.hour_account = format_time(hour_balance)
        employee_ot.save()
        return employee_ot

class AttendanceOverTime(models.Model):
    employee_id = models.ForeignKey(Employee,on_delete=models.CASCADE,related_name='employee_overtime')
    month = models.CharField(max_length=10)
    month_sequence = models.PositiveSmallIntegerField(default=0)
    year = models.CharField(default=datetime.now().strftime('%Y'),null=True,max_length=10)
    hour_account = models.CharField(max_length=10,default='00:00',null=True,validators=[validate_time_format])
    overtime = models.CharField(max_length=20,default='00:00',validators=[validate_time_format])
    hour_account_second = models.IntegerField(default=0,null=True,)
    overtime_second = models.IntegerField(default=0,null=True,)

    class Meta:
        unique_together = [('employee_id'),('month'),('year')]
        ordering = ['-year','-month_sequence']

    
    def save(self, *args, **kwargs):
        self.hour_account_second = strtime_seconds(self.hour_account)
        self.overtime_second = strtime_seconds(self.overtime)
        month_name = self.month.split('-')[0]
        months = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
        self.month_sequence = months.index(month_name)
        super(AttendanceOverTime, self).save(*args, **kwargs)
    


class AttendanceLateComeEarlyOut(models.Model):        
    choices = [
        ('late_come',_('Late Come')),
        ('early_out',_('Early Out')),
    ]

    attendance_id = models.ForeignKey(Attendance,on_delete=models.CASCADE,related_name='late_come_early_out')
    employee_id = models.ForeignKey(Employee,on_delete=models.DO_NOTHING,null=True,related_name='late_come_early_out')
    type = models.CharField(max_length=20,choices=choices)
    class Meta:
        unique_together = [('attendance_id'),('type')]

    def __str__(self) -> str:
        return f'{self.attendance_id.employee_id.employee_first_name} {self.attendance_id.employee_id.employee_last_name} - {self.type}'


class AttendanceValidationCondition(models.Model):
    validation_at_work = models.CharField(default='09:00',max_length=10,validators=[validate_time_format])
    minimum_overtime_to_approve = models.CharField(default='00:30',null=True,max_length=10,validators=[validate_time_format])
    overtime_cutoff = models.CharField(default='02:00',null=True,max_length=10,validators=[validate_time_format])
    def clean(self):
        super().clean()
        if not self.id and AttendanceValidationCondition.objects.exists():
            raise ValidationError(_('You cannot add more conditions.'))