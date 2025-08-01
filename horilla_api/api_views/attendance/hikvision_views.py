import json
from datetime import datetime, date
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from employee.models import Employee
from attendance.models import Attendance, AttendanceActivity
from base.models import EmployeeShift
import logging

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class HikvisionAttendanceReceiveView(APIView):
    """
    API endpoint to receive attendance data from Hikvision device
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            attendance_data = request.data.get('attendance_records', [])
            created_count = 0
            updated_count = 0
            skipped_count = 0

            logger.info(f"Received {len(attendance_data)} attendance records from Hikvision")

            for record in attendance_data:
                try:
                    # Extract record data
                    person_name = record.get('person_name', '').strip()
                    employee_id = record.get('employee_id', '')
                    timestamp_str = record.get('timestamp', '')
                    
                    if not person_name or not timestamp_str:
                        skipped_count += 1
                        continue

                    # Find employee by biometric_employee_name
                    employee = Employee.objects.filter(
                        biometric_employee_name=person_name
                    ).first()

                    if not employee:
                        logger.warning(f"Employee not found: {person_name} (ID: {employee_id})")
                        skipped_count += 1
                        continue

                    # Parse timestamp
                    try:
                        # Handle different timestamp formats
                        if 'T' in timestamp_str:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        else:
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        
                        attendance_date = timestamp.date()
                        clock_in_time = timestamp.time()
                        clock_in_date = timestamp.date()
                        
                    except ValueError as e:
                        logger.error(f"Invalid timestamp format: {timestamp_str}")
                        skipped_count += 1
                        continue

                    # Check if attendance record already exists
                    existing_attendance = Attendance.objects.filter(
                        employee_id=employee,
                        attendance_date=attendance_date
                    ).first()

                    if existing_attendance:
                        # Update if the new check-in time is earlier
                        if (not existing_attendance.attendance_clock_in or 
                            clock_in_time < existing_attendance.attendance_clock_in):
                            
                            existing_attendance.attendance_clock_in = clock_in_time
                            existing_attendance.attendance_clock_in_date = clock_in_date
                            existing_attendance.save()
                            updated_count += 1
                            
                            logger.info(f"Updated attendance for {employee.get_full_name()}: {clock_in_time}")
                        else:
                            skipped_count += 1
                    else:
                        # Create new attendance record
                        try:
                            # Get employee's shift if available
                            shift = self.get_employee_shift(employee)
                            
                            attendance = Attendance.objects.create(
                                employee_id=employee,
                                attendance_date=attendance_date,
                                shift_id=shift,
                                attendance_clock_in_date=clock_in_date,
                                attendance_clock_in=clock_in_time,
                                attendance_validated=False,  # Require manual validation
                                minimum_hour="08:00",  # Default minimum hours
                            )
                            
                            # Also create AttendanceActivity record
                            AttendanceActivity.objects.create(
                                employee_id=employee,
                                attendance_date=attendance_date,
                                clock_in_date=clock_in_date,
                                clock_in=clock_in_time,
                                in_datetime=timestamp,
                            )
                            
                            created_count += 1
                            logger.info(f"Created attendance for {employee.get_full_name()}: {attendance_date} at {clock_in_time}")
                            
                        except Exception as e:
                            logger.error(f"Error creating attendance for {employee.get_full_name()}: {e}")
                            skipped_count += 1

                except Exception as e:
                    logger.error(f"Error processing record: {e}")
                    skipped_count += 1
                    continue

            # Return success response
            response_data = {
                'status': 'success',
                'message': 'Attendance data processed successfully',
                'summary': {
                    'total_records': len(attendance_data),
                    'created': created_count,
                    'updated': updated_count,
                    'skipped': skipped_count
                }
            }
            
            logger.info(f"Hikvision sync completed: {response_data['summary']}")
            return Response(response_data, status=200)

        except Exception as e:
            logger.error(f"Error processing Hikvision attendance data: {e}")
            return Response({
                'status': 'error',
                'message': f'Failed to process attendance data: {str(e)}'
            }, status=400)

    def get_employee_shift(self, employee):
        """Get the employee's default shift"""
        try:
            work_info = getattr(employee, 'employee_work_info', None)
            if work_info:
                return getattr(work_info, 'employee_shift_id', None)
        except AttributeError:
            pass
        
        # Return default shift if available
        return EmployeeShift.objects.first()

