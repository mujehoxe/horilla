"""
views.py

This module contains the view functions for handling HTTP requests and rendering
responses in your application.

Each view function corresponds to a specific URL route and performs the necessary
actions to handle the request, process data, and generate a response.

This module is part of the recruitment project and is intended to
provide the main entry points for interacting with the application's functionality.
"""

import datetime
from django import template
from django.core.mail import EmailMessage
import os
import json
import contextlib
from urllib.parse import parse_qs
from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db.models import ProtectedError
from django.shortcuts import render, redirect
from django.core import serializers
from django.core.paginator import Paginator
from base.context_processors import check_candidate_self_tracking
from base.models import EmailLog, JobPosition
from django.contrib import messages
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext_lazy as _
from employee.models import Employee, EmployeeWorkInformation
from notifications.signals import notify
from horilla import settings
from horilla.decorators import (
    permission_required,
    login_required,
    hx_request_required,
    logger,
)
from base.methods import export_data, generate_pdf, get_key_instances
from recruitment.views.paginator_qry import paginator_qry
from recruitment.pipeline_grouper import group_by_queryset
from recruitment.models import (
    Recruitment,
    Candidate,
    RecruitmentGeneralSetting,
    RejectReason,
    SkillZone,
    SkillZoneCandidate,
    Stage,
    CandidateRating,
    RecruitmentMailTemplate,
    Recruitment,
    Candidate,
    Stage,
    StageFiles,
    StageNote,
)
from recruitment.filters import (
    CandidateFilter,
    CandidateReGroup,
    RecruitmentFilter,
    SkillZoneCandFilter,
    SkillZoneFilter,
    StageFilter,
)
from recruitment.methods import recruitment_manages
from recruitment.decorators import manager_can_enter, recruitment_manager_can_enter
from recruitment.forms import (
    CandidateExportForm,
    RecruitmentCreationForm,
    CandidateCreationForm,
    RejectReasonForm,
    SkillZoneCandidateForm,
    SkillZoneCreateForm,
    StageCreationForm,
    StageDropDownForm,
    CandidateDropDownForm,
    StageNoteForm,
    StageNoteUpdateForm,
    ToSkillZoneForm,
)


def is_stagemanager(request, stage_id=False):
    """
    This method is used to identify the employee is a stage manager or
    not, if stage_id is passed through args, method will
    check the employee is manager to the corresponding stage, return
    tuple with boolean and all stages that employee is manager.
    if called this method without stage_id args it will return boolean
     with all the stage that the employee is stage manager
    Args:
        request : django http request
        stage_id : stage instance id
    """
    user = request.user
    employee = user.employee_get
    if not stage_id:
        return (
            employee.stage_set.exists() or user.is_superuser,
            employee.stage_set.all(),
        )
    stage_obj = Stage.objects.get(id=stage_id)
    return (
        employee in stage_obj.stage_managers.all()
        or user.is_superuser
        or is_recruitmentmanager(request, rec_id=stage_obj.recruitment_id.id)[0],
        employee.stage_set.all(),
    )


def is_recruitmentmanager(request, rec_id=False):
    """
    This method is used to identify the employee is a recruitment
    manager or not, if rec_id is passed through args, method will
    check the employee is manager to the corresponding recruitment,
    return tuple with boolean and all recruitment that employee is manager.
    if called this method without recruitment args it will return
    boolean with all the recruitment that the employee is recruitment manager
    Args:
        request : django http request
        rec_id : recruitment instance id
    """
    user = request.user
    employee = user.employee_get
    if not rec_id:
        return (
            employee.recruitment_set.exists() or user.is_superuser,
            employee.recruitment_set.all(),
        )
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    return (
        employee in recruitment_obj.recruitment_managers.all() or user.is_superuser,
        employee.recruitment_set.all(),
    )


@login_required
@permission_required(perm="recruitment.add_recruitment")
def recruitment(request):
    """
    This method is used to create recruitment, when create recruitment this method
    add  recruitment view,create candidate, change stage sequence and so on, some of
    the permission is checking manually instead of using django permission permission
    to the  recruitment managers
    """
    form = RecruitmentCreationForm()
    if request.method == "POST":
        form = RecruitmentCreationForm(request.POST)
        if form.is_valid():
            recruitment_obj = form.save(commit=False)
            recruitment_obj.save()
            recruitment_obj.recruitment_managers.set(
                Employee.objects.filter(
                    id__in=form.data.getlist("recruitment_managers")
                )
            )
            messages.success(request, _("Recruitment added."))
            with contextlib.suppress(Exception):
                managers = recruitment_obj.recruitment_managers.select_related(
                    "employee_user_id"
                )
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb="You are chosen as one of recruitment manager",
                    verb_ar="تم اختيارك كأحد مديري التوظيف",
                    verb_de="Sie wurden als einer der Personalvermittler ausgewählt",
                    verb_es="Has sido elegido/a como uno de los gerentes de contratación",
                    verb_fr="Vous êtes choisi(e) comme l'un des responsables du recrutement",
                    icon="people-circle",
                    redirect="/recruitment/pipeline",
                )
            return HttpResponse("<script>location.reload();</script>")
    return render(request, "recruitment/recruitment_form.html", {"form": form})


@login_required
@permission_required(perm="recruitment.view_recruitment")
def recruitment_view(request):
    """
    This method is used to  render all recruitment to view
    """
    if not request.GET:
        request.GET.copy().update({"is_active": "on"})
    form = RecruitmentCreationForm()
    queryset = Recruitment.objects.filter(is_active=True)
    if queryset.exists():
        template = "recruitment/recruitment_view.html"
    else:
        template = "recruitment/recruitment_empty.html"
    filter_obj = RecruitmentFilter(request.GET, queryset)
    return render(
        request,
        template,
        {
            "data": paginator_qry(filter_obj.qs, request.GET.get("page")),
            "f": filter_obj,
            "form": form,
        },
    )


@login_required
@permission_required(perm="recruitment.change_recruitment")
@hx_request_required
def recruitment_update(request, rec_id):
    """
    This method is used to update the recruitment, when updating the recruitment,
    any changes in manager is exists then permissions also assigned to the manager
    Args:
        id : recruitment_id
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    form = RecruitmentCreationForm(instance=recruitment_obj)
    if request.method == "POST":
        form = RecruitmentCreationForm(request.POST, instance=recruitment_obj)
        if form.is_valid():
            recruitment_obj = form.save()
            messages.success(request, _("Recruitment Updated."))
            response = render(
                request, "recruitment/recruitment_form.html", {"form": form}
            )
            with contextlib.suppress(Exception):
                managers = recruitment_obj.recruitment_managers.select_related(
                    "employee_user_id"
                )
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb=f"{recruitment_obj} is updated, You are chosen as one of the managers",
                    verb_ar=f"{recruitment_obj} تم تحديثه، تم اختيارك كأحد المديرين",
                    verb_de=f"{recruitment_obj} wurde aktualisiert. Sie wurden als\
                            einer der Manager ausgewählt",
                    verb_es=f"{recruitment_obj} ha sido actualizado/a. Has sido elegido\
                            a como uno de los gerentes",
                    verb_fr=f"{recruitment_obj} a été mis(e) à jour. Vous êtes choisi(e) comme\
                            l'un des responsables",
                    icon="people-circle",
                    redirect="/recruitment/pipeline",
                )

            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(request, "recruitment/recruitment_update_form.html", {"form": form})


@login_required
@manager_can_enter(perm="recruitment.view_recruitment")
def recruitment_pipeline(request):
    """
    This method is used to filter out candidate through pipeline structure
    """
    view = request.GET.get("view")

    filter_obj = RecruitmentFilter(request.GET)
    # is active filteration not providing on pipeline
    recruitments = filter_obj.qs.filter(is_active=True)
    
    if request.GET.get("closed") == "closed":
        rec = Recruitment.objects.filter(closed=True)
        if rec.exists() and view == "card":
            template = "pipeline/pipeline_card.html"
        elif rec.exists():
            template = "pipeline/pipeline.html"
        else:
            template = "pipeline/pipeline_empty.html"
    else:
        rec = Recruitment.objects.filter(closed=False)
        if rec.exists():
            template = "pipeline/pipeline.html"
        else:
            template = "pipeline/pipeline_empty.html"
        if view == "card":
            template = "pipeline/pipeline_card.html"
    recruitment_form = RecruitmentCreationForm()
    stage_form = StageDropDownForm()
    candidate_form = CandidateDropDownForm()
    
    status = request.GET.get("closed")
    if not status:
        recruitments = recruitments.filter(closed=False)
    if request.method == "POST":
        if request.FILES.get("resume") is not None:
            if request.user.has_perm("add_candidate") or is_stagemanager(
                request,
            ):
                candidate_form = CandidateDropDownForm(request.POST, request.FILES)
                if candidate_form.is_valid():
                    candidate_obj = candidate_form.save()
                    candidate_form = CandidateDropDownForm()
                    with contextlib.suppress(Exception):
                        managers = candidate_obj.stage_id.stage_managers.select_related(
                            "employee_user_id"
                        )
                        users = [employee.employee_user_id for employee in managers]
                        notify.send(
                            request.user.employee_get,
                            recipient=users,
                            verb=f"New candidate arrived on stage {candidate_obj.stage_id.stage}",
                            verb_ar=f"وصل مرشح جديد إلى المرحلة {candidate_obj.stage_id.stage}",
                            verb_de=f"Neuer Kandidat ist auf der Stufe\
                                    {candidate_obj.stage_id.stage} angekommen",
                            verb_es=f"Nuevo candidato llegó a la etapa {candidate_obj.stage_id.stage}",
                            verb_fr=f"Nouveau candidat arrivé à l'étape {candidate_obj.stage_id.stage}",
                            icon="person-add",
                            redirect="/recruitment/pipeline",
                        )

                    messages.success(request, _("Candidate added."))
                    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
        elif request.POST.get("stage_managers") and request.user.has_perm("add_stage"):
            stage_form = StageDropDownForm(request.POST)
            if stage_form.is_valid():
                if recruitment_manages(
                    request, stage_form.instance.recruitment_id
                ) or request.user.has_perm("recruitment.add_stage"):
                    stage_obj = stage_form.save()
                    stage_form = StageDropDownForm()
                    messages.success(request, _("Stage added."))
                    with contextlib.suppress(Exception):
                        managers = stage_obj.stage_managers.select_related(
                            "employee_user_id"
                        )
                        users = [employee.employee_user_id for employee in managers]
                        notify.send(
                            request.user.employee_get,
                            recipient=users,
                            verb=f"You are chosen as a stage manager on the stage\
                                      {stage_obj.stage} in recruitment {stage_obj.recruitment_id}",
                            verb_ar=f"لقد تم اختيارك كمدير مرحلة في المرحلة \
                                    {stage_obj.stage} في التوظيف {stage_obj.recruitment_id}",
                            verb_de=f"Sie wurden als Bühnenmanager für die Stufe{stage_obj.stage}\
                                  in der Rekrutierung {stage_obj.recruitment_id} ausgewählt",
                            verb_es=f"Has sido elegido/a como gerente de etapa en la etapa\
                                      {stage_obj.stage} en la contratación {stage_obj.recruitment_id}",
                            verb_fr=f"Vous avez été choisi(e) comme responsable de l'étape\
                                      {stage_obj.stage} dans le recrutement {stage_obj.recruitment_id}",
                            icon="people-circle",
                            redirect="/recruitment/pipeline",
                        )

                    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
                messages.info(request, _("You dont have access"))
    previous_data = request.GET.urlencode()
    paginator = Paginator(recruitments, 4)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    groups = []
    for rec in page_obj:
        stages = StageFilter(request.GET, queryset=rec.stage_set.all()).qs
        all_stages_grouper = []
        for stage_in_all in stages.order_by("sequence"):
            all_stages_grouper.append({"grouper": stage_in_all, "list": []})
        data = {"recruitment": rec, "stages": []}
        for stage in stages.order_by("sequence"):
            stage_candidates = CandidateFilter(
                request.GET,
                stage.candidate_set.order_by("sequence").filter(
                    is_active=True,
                ),
            ).qs

            page_name = "page" + stage.stage + str(rec.id)
            grouper = group_by_queryset(
                stage_candidates,
                "stage_id",
                request.GET.get(page_name),
                page_name,
            ).object_list
            data["stages"] = data["stages"] + grouper
        existing_grouper_ids = {item["grouper"].id for item in data["stages"]}
        for item in all_stages_grouper:
            if item["grouper"].id not in existing_grouper_ids:
                data["stages"].append(
                    {
                        "grouper": item["grouper"],
                        "list": [],
                        "dynamic_name": f'dynamic_page_page{item["grouper"].id}',
                    }
                )

        groups.append(data)

    for item in groups:
        setattr(item["recruitment"], "stages", item["stages"])
    filter_dict = parse_qs(request.GET.urlencode())
    if not request.GET.get("closed"):
        filter_obj.form.initial["closed"] = False
        filter_dict["closed"] = ["false"]
    for key, val in filter_dict.copy().items():
        if val[0] == "unknown" or key == "view":
            del filter_dict[key]
    return render(
        request,
        template,
        {
            "recruitment": page_obj,
            "rec_filter_obj": filter_obj,
            "stage_filter_obj": StageFilter(request.GET),
            "candidate_filter_obj": CandidateFilter(request.GET),
            "filter_dict": filter_dict,
            "form": recruitment_form,
            "stage_form": stage_form,
            "candidate_form": candidate_form,
            "status": status,
            "view": view,
            "pd": previous_data,
        },
    )


@login_required
@permission_required(perm="recruitment.view_recruitment")
def recruitment_pipeline_card(request):
    """
    This method is used to render pipeline card structure.
    """
    search = request.GET.get("search")
    search = search if search is not None else ""
    recruitment_obj = Recruitment.objects.all()
    candidates = Candidate.objects.filter(name__icontains=search, is_active=True)
    stages = Stage.objects.all()
    return render(
        request,
        "pipeline/pipeline_components/pipeline_card_view.html",
        {"recruitment": recruitment_obj, "candidates": candidates, "stages": stages},
    )


@login_required
@recruitment_manager_can_enter(perm="recruitment.change_stage")
def stage_update_pipeline(request, stage_id):
    """
    This method is used to update stage from pipeline view
    """
    stage_obj = Stage.objects.get(id=stage_id)
    form = StageCreationForm(instance=stage_obj)
    if request.POST:
        form = StageCreationForm(request.POST, instance=stage_obj)
        if form.is_valid():
            stage_obj = form.save()
            messages.success(request, _("Stage updated."))
            with contextlib.suppress(Exception):
                managers = stage_obj.stage_managers.select_related("employee_user_id")
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb=f"{stage_obj.stage} stage in recruitment {stage_obj.recruitment_id}\
                            is updated, You are chosen as one of the managers",
                    verb_ar=f"تم تحديث مرحلة {stage_obj.stage} في التوظيف {stage_obj.recruitment_id}\
                            ، تم اختيارك كأحد المديرين",
                    verb_de=f"Die Stufe {stage_obj.stage} in der Rekrutierung {stage_obj.recruitment_id}\
                            wurde aktualisiert. Sie wurden als einer der Manager ausgewählt",
                    verb_es=f"Se ha actualizado la etapa {stage_obj.stage} en la contratación\
                          {stage_obj.recruitment_id}.Has sido elegido/a como uno de los gerentes",
                    verb_fr=f"L'étape {stage_obj.stage} dans le recrutement {stage_obj.recruitment_id}\
                          a été mise à jour.Vous avez été choisi(e) comme l'un des responsables",
                    icon="people-circle",
                    redirect="/recruitment/pipeline",
                )

            return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

    return render(request, "pipeline/form/stage_update.html", {"form": form})


@login_required
@recruitment_manager_can_enter(perm="recruitment.change_recruitment")
def recruitment_update_pipeline(request, rec_id):
    """
    This method is used to update recruitment from pipeline view
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    form = RecruitmentCreationForm(instance=recruitment_obj)
    if request.POST:
        form = RecruitmentCreationForm(request.POST, instance=recruitment_obj)
        if form.is_valid():
            recruitment_obj = form.save()
            messages.success(request, _("Recruitment updated."))
            with contextlib.suppress(Exception):
                managers = recruitment_obj.recruitment_managers.select_related(
                    "employee_user_id"
                )
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb=f"{recruitment_obj} is updated, You are chosen as one of the managers",
                    verb_ar=f"تم تحديث {recruitment_obj}، تم اختيارك كأحد المديرين",
                    verb_de=f"{recruitment_obj} wurde aktualisiert.\
                          Sie wurden als einer der Manager ausgewählt",
                    verb_es=f"{recruitment_obj} ha sido actualizado/a. Has sido elegido\
                            a como uno de los gerentes",
                    verb_fr=f"{recruitment_obj} a été mis(e) à jour. Vous avez été\
                            choisi(e) comme l'un des responsables",
                    icon="people-circle",
                    redirect="/recruitment/pipeline",
                )

            response = render(
                request, "pipeline/form/recruitment_update.html", {"form": form}
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(request, "pipeline/form/recruitment_update.html", {"form": form})


@login_required
@recruitment_manager_can_enter(perm="recruitment.change_recruitment")
def recruitment_close_pipeline(request, rec_id):
    """
    This method is used to close recruitment from pipeline view
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    recruitment_obj.closed = True
    recruitment_obj.save()

    messages.success(request, "Recruitment closed successfully")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@recruitment_manager_can_enter(perm="recruitment.change_recruitment")
def recruitment_reopen_pipeline(request, rec_id):
    """
    This method is used to re-open recruitment from pipeline view
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    recruitment_obj.closed = False
    recruitment_obj.save()

    messages.success(request, "Recruitment re-opend successfully")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def candidate_stage_update(request, cand_id):
    """
    This method is a ajax method used to update candidate stage when drag and drop
    the candidate from one stage to another on the pipeline template
    Args:
        id : candidate_id
    """
    stage_id = request.POST["stageId"]
    candidate_obj = Candidate.objects.get(id=cand_id)
    history_queryset = candidate_obj.history_set.all().first()
    stage_obj = Stage.objects.get(id=stage_id)
    previous_stage = history_queryset.stage_id
    if previous_stage == stage_obj:
        return JsonResponse({"type": "noChange", "message": _("No change detected.")})
    # Here set the last updated schedule date on this stage if schedule exists in history
    history_queryset = candidate_obj.history_set.filter(stage_id=stage_obj)
    schedule_date = None
    if history_queryset.exists():
        # this condition is executed when a candidate dropped back to any previous
        # stage, if there any scheduled date then set it back
        schedule_date = history_queryset.first().schedule_date
    stage_manager_on_this_recruitment = (
        is_stagemanager(request)[1]
        .filter(recruitment_id=stage_obj.recruitment_id)
        .exists()
    )
    if (
        stage_manager_on_this_recruitment
        or request.user.is_superuser
        or is_recruitmentmanager(rec_id=stage_obj.recruitment_id.id)[0]
    ):
        candidate_obj.stage_id = stage_obj
        candidate_obj.schedule_date = None
        candidate_obj.hired = stage_obj.stage_type == "hired"
        candidate_obj.schedule_date = schedule_date
        candidate_obj.start_onboard = False
        candidate_obj.save()
        with contextlib.suppress(Exception):
            managers = stage_obj.stage_managers.select_related("employee_user_id")
            users = [employee.employee_user_id for employee in managers]
            notify.send(
                request.user.employee_get,
                recipient=users,
                verb=f"New candidate arrived on stage {stage_obj.stage}",
                verb_ar=f"وصل مرشح جديد إلى المرحلة {stage_obj.stage}",
                verb_de=f"Neuer Kandidat ist auf der Stufe {stage_obj.stage} angekommen",
                verb_es=f"Nuevo candidato llegó a la etapa {stage_obj.stage}",
                verb_fr=f"Nouveau candidat arrivé à l'étape {stage_obj.stage}",
                icon="person-add",
                redirect="/recruitment/pipeline",
            )

        return JsonResponse(
            {"type": "success", "message": _("Candidate stage updated")}
        )
    return JsonResponse(
        {"type": "danger", "message": _("Something went wrong, Try agian.")}
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.view_stagenote")
def view_note(request, cand_id):
    """
    This method renders a template components to view candidate remark or note
    Args:
        id : candidate instance id
    """
    candidate_obj = Candidate.objects.get(id=cand_id)
    notes = candidate_obj.stagenote_set.all().order_by("-id")
    return render(
        request,
        "pipeline/pipeline_components/view_note.html",
        {"cand": candidate_obj, "notes": notes},
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.add_stagenote")
def add_note(request, cand_id=None):
    """
    This method renders template component to add candidate remark
    """
    form = StageNoteForm(initial={"candidate_id": cand_id})
    if request.method == "POST":
        form = StageNoteForm(
            request.POST,
            request.FILES,
        )
        if form.is_valid():
            note, attachment_ids = form.save(commit=False)
            note.stage_id = note.candidate_id.stage_id
            note.updated_by = request.user.employee_get
            note.save()
            note.stage_files.set(attachment_ids)
            messages.success(request, _("Note added successfully.."))
            response = render(
                request, "pipeline/pipeline_components/add_note.html", {"form": form}
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(
        request,
        "pipeline/pipeline_components/add_note.html",
        {
            "note_form": form,
        },
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.add_stagenote")
def create_note(request, cand_id=None):
    """
    This method renders template component to add candidate remark
    """
    form = StageNoteForm(initial={"candidate_id": cand_id})
    if request.method == "POST":
        form = StageNoteForm(request.POST, request.FILES)
        if form.is_valid():
            candidate = form.cleaned_data.get("candidate_id")
            cand_id = candidate.id
            note, attachment_ids = form.save(commit=False)
            note.stage_id = note.candidate_id.stage_id
            note.updated_by = request.user.employee_get
            note.save()
            note.stage_files.set(attachment_ids)
            messages.success(request, _("Note added successfully.."))
            return redirect("view-note", cand_id=cand_id)

    return render(
        request,
        "pipeline/pipeline_components/create_note.html",
        {
            "note_form": form,
        },
    )


@login_required
@manager_can_enter(perm="recruitment.change_stagenote")
def note_update(request, note_id):
    """
    This method is used to update the stage not
    Args:
        id : stage note instance id
    """
    note = StageNote.objects.get(id=note_id)
    form = StageNoteUpdateForm(instance=note)
    if request.POST:
        form = StageNoteUpdateForm(request.POST, request.FILES, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, _("Note updated successfully..."))
            cand_id = note.candidate_id.id
            return redirect("view-note", cand_id=cand_id)

    return render(
        request, "pipeline/pipeline_components/update_note.html", {"form": form}
    )


@login_required
@manager_can_enter(perm="recruitment.change_stagenote")
def note_update_individual(request, note_id):
    """
    This method is used to update the stage not
    Args:
        id : stage note instance id
    """
    note = StageNote.objects.get(id=note_id)
    form = StageNoteForm(instance=note)
    if request.POST:
        form = StageNoteForm(request.POST, request.FILES, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, _("Note updated successfully..."))
            response = render(
                request,
                "pipeline/pipeline_components/update_note_individual.html",
                {"form": form},
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(
        request,
        "pipeline/pipeline_components/update_note_individual.html",
        {
            "form": form,
        },
    )


@login_required
@hx_request_required
def add_more_files(request, id):
    """
    This method is used to Add more files to the stage candidate note.
    Args:
        id : stage note instance id
    """
    note = StageNote.objects.get(id=id)
    if request.method == "POST":
        files = request.FILES.getlist("files")
        files_ids = []
        for file in files:
            instance = StageFiles.objects.create(files=file)
            files_ids.append(instance.id)

            note.stage_files.add(instance.id)
    return redirect("view-note", cand_id=note.candidate_id.id)


@login_required
def delete_stage_note_file(request, id):
    """
    This method is used to delete the stage note file
    Args:
        id : stage file instance id
    """
    file = StageFiles.objects.get(id=id)
    cand_id = file.stagenote_set.all().first().candidate_id.id
    file.delete()
    return redirect("view-note", cand_id=cand_id)


@login_required
@permission_required(perm="recruitment.change_candidate")
def candidate_schedule_date_update(request):
    """
    This is a an ajax method to update schedule date for a candidate
    """
    candidate_id = request.POST["candidateId"]
    schedule_date = request.POST["date"]
    candidate_obj = Candidate.objects.get(id=candidate_id)
    candidate_obj.schedule_date = schedule_date
    candidate_obj.save()
    return JsonResponse({"message": "congratulations"})


@login_required
@manager_can_enter(perm="recruitment.add_stage")
def stage(request):
    """
    This method is used to create stages, also several permission assigned to the stage managers
    """
    form = StageCreationForm(
        initial={"recruitment_id": request.GET.get("recruitment_id")}
    )
    if request.method == "POST":
        form = StageCreationForm(request.POST)
        if form.is_valid():
            stage_obj = form.save()
            stage_obj.stage_managers.set(
                Employee.objects.filter(id__in=form.data.getlist("stage_managers"))
            )
            stage_obj.save()
            recruitment_obj = stage_obj.recruitment_id
            rec_stages = (
                Stage.objects.filter(recruitment_id=recruitment_obj, is_active=True)
                .order_by("sequence")
                .last()
            )
            if rec_stages.sequence is None:
                stage_obj.sequence = 1
            else:
                stage_obj.sequence = rec_stages.sequence + 1
            stage_obj.save()
            messages.success(request, _("Stage added."))
            with contextlib.suppress(Exception):
                managers = stage_obj.stage_managers.select_related("employee_user_id")
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb=f"Stage {stage_obj} is updated on recruitment {stage_obj.recruitment_id},\
                          You are chosen as one of the managers",
                    verb_ar=f"تم تحديث المرحلة {stage_obj} في التوظيف\
                          {stage_obj.recruitment_id}، تم اختيارك كأحد المديرين",
                    verb_de=f"Stufe {stage_obj} wurde in der Rekrutierung {stage_obj.recruitment_id}\
                          aktualisiert. Sie wurden als einer der Manager ausgewählt",
                    verb_es=f"La etapa {stage_obj} ha sido actualizada en la contratación\
                          {stage_obj.recruitment_id}. Has sido elegido/a como uno de los gerentes",
                    verb_fr=f"L'étape {stage_obj} a été mise à jour dans le recrutement\
                          {stage_obj.recruitment_id}. Vous avez été choisi(e) comme l'un des responsables",
                    icon="people-circle",
                    redirect="/recruitment/pipeline",
                )

            return HttpResponse("<script>location.reload();</script>")
    return render(request, "stage/stage_form.html", {"form": form})


@login_required
@permission_required(perm="recruitment.view_stage")
def stage_view(request):
    """
    This method is used to render all stages to a template
    """
    stages = Stage.objects.filter()
    filter_obj = StageFilter()
    form = StageCreationForm()
    if stages.exists():
        template = "stage/stage_view.html"
    else:
        template = "stage/stage_empty.html"
    return render(
        request,
        template,
        {
            "data": paginator_qry(stages, request.GET.get("page")),
            "form": form,
            "f": filter_obj,
        },
    )


@login_required
@manager_can_enter(perm="recruitment.change_stage")
@hx_request_required
def stage_update(request, stage_id):
    """
    This method is used to update stage, if the managers changed then\
    permission assigned to new managers also
    Args:
        id : stage_id

    """
    stages = Stage.objects.get(id=stage_id)
    form = StageCreationForm(instance=stages)
    if request.method == "POST":
        form = StageCreationForm(request.POST, instance=stages)
        if form.is_valid():
            form.save()
            messages.success(request, _("Stage updated."))
            response = render(
                request, "recruitment/recruitment_form.html", {"form": form}
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(request, "stage/stage_update_form.html", {"form": form})


@login_required
@require_http_methods(["POST"])
@hx_request_required
def stage_title_update(request, stage_id):
    """
    This method is used to update the name of recruitment stage
    """
    stage_obj = Stage.objects.get(id=stage_id)
    stage_obj.stage = request.POST["stage"]
    stage_obj.save()
    message = _("The stage title has been updated successfully")
    return HttpResponse(
        f'<div class="oh-alert-container"><div class="oh-alert oh-alert--animated oh-alert--success">{message}</div></div>'
    )


@login_required
@permission_required(perm="recruitment.add_candidate")
def candidate(request):
    """
    This method used to create candidate
    """
    form = CandidateCreationForm()
    open_recruitment = Recruitment.objects.filter(closed=False, is_active=True)
    path = "/recruitment/candidate-view"
    if request.method == "POST":
        form = CandidateCreationForm(request.POST, request.FILES)
        if form.is_valid():
            candidate_obj = form.save(commit=False)
            candidate_obj.start_onboard = False
            if candidate_obj.stage_id is None:
                candidate_obj.stage_id = Stage.objects.filter(
                    recruitment_id=candidate_obj.recruitment_id, stage_type="initial"
                ).first()
            # when creating new candidate from onboarding view
            if request.GET.get("onboarding") == "True":
                candidate_obj.hired = True
                path = "/onboarding/candidates-view"
            candidate_obj.save()
            messages.success(request, _("Candidate added."))
            return redirect(path)

    return render(
        request,
        "candidate/candidate_create_form.html",
        {"form": form, "open_recruitment": open_recruitment},
    )


@login_required
@permission_required(perm="recruitment.add_candidate")
def recruitment_stage_get(_, rec_id):
    """
    This method returns all stages as json
    Args:
        id: recruitment_id
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    all_stages = recruitment_obj.stage_set.all()
    all_stage_json = serializers.serialize("json", all_stages)
    return JsonResponse({"stages": all_stage_json})


@login_required
@permission_required(perm="recruitment.view_candidate")
def candidate_view(request):
    """
    This method render all candidate to the template
    """
    view_type = request.GET.get("view")
    previous_data = request.GET.urlencode()
    candidates = Candidate.objects.filter(is_active=True)
    candidate_all = Candidate.objects.all()

    mails = list(Candidate.objects.values_list("email", flat=True))
    # Query the User model to check if any email is present
    existing_emails = list(
        User.objects.filter(username__in=mails).values_list("email", flat=True)
    )

    filter_obj = CandidateFilter(request.GET, queryset=candidates)
    export_fields = CandidateExportForm()
    export_obj = CandidateFilter(request.GET, queryset=candidates)
    if candidate_all.exists():
        template = "candidate/candidate_view.html"
    else:
        template = "candidate/candidate_empty.html"
    data_dict = parse_qs(previous_data)
    get_key_instances(Candidate, data_dict)
    return render(
        request,
        template,
        {
            "data": paginator_qry(filter_obj.qs, request.GET.get("page")),
            "pd": previous_data,
            "f": filter_obj,
            "export_fields": export_fields,
            "export_obj": export_obj,
            "view_type": view_type,
            "filter_dict": data_dict,
            "gp_fields": CandidateReGroup.fields,
            "emp_list": existing_emails,
        },
    )


@login_required
def candidate_export(request):
    """
    This method is used to Export candidate data
    """
    return export_data(
        request=request,
        model=Candidate,
        filter_class=CandidateFilter,
        form_class=CandidateExportForm,
        file_name="Candidate_export",
    )


@login_required
@permission_required(perm="recruitment.view_candidate")
def candidate_view_list(request):
    """
    This method renders all candidate on candidate_list.html template
    """
    previous_data = request.GET.urlencode()
    candidates = Candidate.objects.all()
    if request.GET.get("is_active") is None:
        candidates = candidates.filter(is_active=True)
    candidates = CandidateFilter(request.GET, queryset=candidates).qs
    return render(
        request,
        "candidate/candidate_list.html",
        {
            "data": paginator_qry(candidates, request.GET.get("page")),
            "pd": previous_data,
        },
    )


@login_required
@permission_required(perm="recruitment.view_candidate")
def candidate_view_card(request):
    """
    This method renders all candidate on candidate_card.html template
    """
    previous_data = request.GET.urlencode()
    candidates = Candidate.objects.all()
    if request.GET.get("is_active") is None:
        candidates = candidates.filter(is_active=True)
    candidates = CandidateFilter(request.GET, queryset=candidates).qs
    return render(
        request,
        "candidate/candidate_card.html",
        {
            "data": paginator_qry(candidates, request.GET.get("page")),
            "pd": previous_data,
        },
    )


@login_required
@permission_required(perm="recruitment.view_candidate")
def candidate_view_individual(request, cand_id, **kwargs):
    """
    This method is used to view profile of candidate.
    """
    candidate_obj = Candidate.objects.get(id=cand_id)

    mails = list(Candidate.objects.values_list("email", flat=True))
    # Query the User model to check if any email is present
    existing_emails = list(
        User.objects.filter(username__in=mails).values_list("email", flat=True)
    )
    ratings = candidate_obj.candidate_rating.all()
    rating_list = []
    avg_rate = 0
    for rating in ratings:
        rating_list.append(rating.rating)
    if len(rating_list) != 0:
        avg_rate = round(sum(rating_list) / len(rating_list))

    return render(
        request,
        "candidate/individual.html",
        {
            "candidate": candidate_obj,
            "emp_list": existing_emails,
            "average_rate": avg_rate,
        },
    )


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def candidate_update(request, cand_id, **kwargs):
    """
    Used to update or change the candidate
    Args:
        id : candidate_id
    """
    candidate_obj = Candidate.objects.get(id=cand_id)
    form = CandidateCreationForm(instance=candidate_obj)
    path = "/recruitment/candidate-view"
    if request.method == "POST":
        form = CandidateCreationForm(
            request.POST, request.FILES, instance=candidate_obj
        )
        if form.is_valid():
            candidate_obj = form.save()
            if candidate_obj.stage_id is None:
                candidate_obj.stage_id = Stage.objects.filter(
                    recruitment_id=candidate_obj.recruitment_id, stage_type="initial"
                ).first()
            if candidate_obj.stage_id is not None:
                if (
                    candidate_obj.stage_id.recruitment_id
                    != candidate_obj.recruitment_id
                ):
                    candidate_obj.stage_id = (
                        candidate_obj.recruitment_id.stage_set.filter(
                            stage_type="initial"
                        ).first()
                    )
            if request.GET.get("onboarding") == "True":
                candidate_obj.hired = True
                path = "/onboarding/candidates-view"
            candidate_obj.save()
            messages.success(request, _("Candidate Updated Successfully."))
            return redirect(path)
    return render(request, "candidate/candidate_create_form.html", {"form": form})


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def candidate_conversion(request, cand_id, **kwargs):
    """
    This method is used to convert a candidate into employee
    Args:
        cand_id : candidate instance id
    """
    candidate_obj = Candidate.objects.filter(id=cand_id)
    for detail in candidate_obj:
        can_name = detail.name
        can_mob = detail.mobile
        can_job = detail.job_position_id
        can_dep = can_job.department_id
        can_mail = detail.email
        can_gender = detail.gender
        can_company = detail.recruitment_id.company_id

    user_exists = User.objects.filter(email=can_mail).exists()
    if user_exists:
        messages.error(request, _("Employee instance already exist"))
    elif not Employee.objects.filter(email=can_mail).exists():
        new_employee = Employee.objects.create(
            employee_first_name=can_name,
            email=can_mail,
            phone=can_mob,
            gender=can_gender,
        )
        new_employee.save()
        EmployeeWorkInformation.objects.create(
            employee_id=new_employee,
            job_position_id=can_job,
            department_id=can_dep,
            company_id=can_company,
        )
        messages.success(request, _("Employee instance created successfully"))
    else:
        messages.info(request, "A employee with this mail already exists")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def delete_profile_image(request, obj_id):
    """
    This method is used to delete the profile image of the candidate
    Args:
        obj_id : candidate instance id
    """
    candidate_obj = Candidate.objects.get(id=obj_id)
    try:
        if candidate_obj.profile:
            file_path = candidate_obj.profile.path
            absolute_path = os.path.join(settings.MEDIA_ROOT, file_path)
            os.remove(absolute_path)
            candidate_obj.profile = None
            candidate_obj.save()
            messages.success(request, _("Profile image removed."))
    except Exception as e:
        pass
    return redirect("rec-candidate-update", cand_id=obj_id)


@login_required
@permission_required(perm="recruitment.view_history")
def candidate_history(request, cand_id):
    """
    This method is used to view candidate stage changes
    Args:
        id : candidate_id
    """
    candidate_obj = Candidate.objects.get(id=cand_id)
    candidate_history_queryset = candidate_obj.history.all()
    return render(
        request,
        "candidate/candidate_history.html",
        {"history": candidate_history_queryset},
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.change_candidate")
def form_send_mail(request, cand_id):
    """
    This method is used to render the bootstrap modal content body form
    """
    candidate_obj = Candidate.objects.get(id=cand_id)
    templates = RecruitmentMailTemplate.objects.all()
    return render(
        request,
        "pipeline/pipeline_components/send_mail.html",
        {"cand": candidate_obj, "templates": templates},
    )


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def send_acknowledgement(request):
    """
    This method is used to send acknowledgement mail to the candidate
    """
    candidate_id = request.POST["id"]
    subject = request.POST.get("subject")
    bdy = request.POST.get("body")
    other_attachments = request.FILES.getlist("other_attachments")
    attachments = [
        (file.name, file.read(), file.content_type) for file in other_attachments
    ]
    host = settings.EMAIL_HOST_USER
    candidate_obj = Candidate.objects.get(id=candidate_id)
    template_attachment_ids = request.POST.getlist("template_attachments")
    bodys = list(
        RecruitmentMailTemplate.objects.filter(
            id__in=template_attachment_ids
        ).values_list("body", flat=True)
    )
    for html in bodys:
        # due to not having solid template we first need to pass the context
        template_bdy = template.Template(html)
        context = template.Context(
            {"instance": candidate_obj, "self": request.user.employee_get}
        )
        render_bdy = template_bdy.render(context)
        attachments.append(
            (
                "Document",
                generate_pdf(render_bdy, {}, path=False, title="Document").content,
                "application/pdf",
            )
        )

    template_bdy = template.Template(bdy)
    context = template.Context(
        {"instance": candidate_obj, "self": request.user.employee_get}
    )
    render_bdy = template_bdy.render(context)
    to = request.POST["to"]
    email = EmailMessage(
        subject,
        render_bdy,
        host,
        [to],
    )
    email.content_subtype = "html"

    email.attachments = attachments
    try:
        email.send()
        messages.success(request, "Mail sent to candidate")
    except Exception as e:
        logger.exception(e)
        messages.error(request, "Something went wrong")
    return HttpResponse("<script>window.location.reload()</script>")


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def candidate_sequence_update(request):
    """
    This method is used to update the sequence of candidate
    """
    sequence_data = json.loads(request.POST["sequenceData"])
    for cand_id, seq in sequence_data.items():
        cand = Candidate.objects.get(id=cand_id)
        cand.sequence = seq
        cand.save()

    return JsonResponse({"message": "Sequence updated", "type": "info"})


@login_required
@recruitment_manager_can_enter(perm="recruitment.change_stage")
def stage_sequence_update(request):
    """
    This method is used to update the sequence of the stages
    """
    sequence_data = json.loads(request.POST["sequence"])
    for stage_id, seq in sequence_data.items():
        stage = Stage.objects.get(id=stage_id)
        stage.sequence = seq
        stage.save()
    return JsonResponse({"type": "success", "message": "Stage sequence updated"})


@login_required
def candidate_select(request):
    """
    This method is used for select all in candidate
    """
    page_number = request.GET.get("page")

    if page_number == "all":
        employees = Candidate.objects.filter(is_active=True)
    else:
        employees = Candidate.objects.all()

    employee_ids = [str(emp.id) for emp in employees]
    total_count = employees.count()

    context = {"employee_ids": employee_ids, "total_count": total_count}

    return JsonResponse(context, safe=False)


@login_required
def candidate_select_filter(request):
    """
    This method is used to select all filtered candidates
    """
    page_number = request.GET.get("page")
    filtered = request.GET.get("filter")
    filters = json.loads(filtered) if filtered else {}

    if page_number == "all":
        candidate_filter = CandidateFilter(filters, queryset=Candidate.objects.all())

        # Get the filtered queryset
        filtered_candidates = candidate_filter.qs

        employee_ids = [str(emp.id) for emp in filtered_candidates]
        total_count = filtered_candidates.count()

        context = {"employee_ids": employee_ids, "total_count": total_count}

        return JsonResponse(context)


@login_required
def create_candidate_rating(request, cand_id):
    """
    This method is used to create rating for the candidate
    Args:
        cand_id : candidate instance id
    """
    cand_id = cand_id
    candidate = Candidate.objects.get(id=cand_id)
    employee_id = request.user.employee_get
    rating = request.POST.get("rating")
    CandidateRating.objects.create(
        candidate_id=candidate, rating=rating, employee_id=employee_id
    )
    return redirect(recruitment_pipeline)


# ///////////////////////////////////////////////
# skill zone
# ///////////////////////////////////////////////


@login_required
@manager_can_enter(perm="recruitment.view_skillzone")
def skill_zone_view(request):
    """
    This method is used to show Skill zone view
    """
    skill_zones = SkillZone.objects.filter(is_active=True)
    skill_zones_filtered = SkillZoneFilter(request.GET, queryset=skill_zones).qs
    previous_data = request.GET.urlencode()
    data_dict = parse_qs(previous_data)
    get_key_instances(SkillZone, data_dict)
    if skill_zones.exists():
        template = "skill_zone/skill_zone_view.html"
    else:
        template = "skill_zone/empty_skill_zone.html"

    context = {
        "skill_zones": paginator_qry(skill_zones_filtered, request.GET.get("page")),
        "page": request.GET.get("page"),
        "pd": previous_data,
        "f": SkillZoneFilter(),
        "filter_dict": data_dict,
    }
    return render(request, template, context=context)


@login_required
@manager_can_enter(perm="recruitment.add_skillzone")
def skill_zone_create(request):
    """
    This method is used to create Skill zone.
    """
    form = SkillZoneCreateForm()
    if request.method == "POST":
        form = SkillZoneCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Skill Zone created successfully."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "skill_zone/skill_zone_create.html",
        {"form": form},
    )


@login_required
@manager_can_enter(perm="recruitment.change_skillzone")
def skill_zone_update(request, sz_id):
    """
    This method is used to update Skill zone.
    """
    skill_zone = SkillZone.objects.get(id=sz_id)
    form = SkillZoneCreateForm(instance=skill_zone)
    if request.method == "POST":
        form = SkillZoneCreateForm(request.POST, instance=skill_zone)
        if form.is_valid():
            form.save()
            messages.success(request, _("Skill Zone updated successfully."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "skill_zone/skill_zone_update.html",
        {"form": form, "sz_id": sz_id},
    )


@login_required
@manager_can_enter(perm="recruitment.delete_skillzone")
def skill_zone_delete(request, sz_id):
    """
    function used to delete Skill zone.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_id : Skill zone id

    Returns:
    GET : return Skill zone view template
    """
    try:
        SkillZone.objects.get(id=sz_id).delete()
        messages.success(request, _("Skill zone deleted successfully.."))
    except SkillZone.DoesNotExist:
        messages.error(request, _("Skill zone not found."))
    except ProtectedError:
        messages.error(request, _("Related entries exists"))
    return redirect(skill_zone_view)


@login_required
@manager_can_enter(perm="recruitment.delete_skillzone")
def skill_zone_archive(request, sz_id):
    """
    function used to archive or un-archive Skill zone.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_id : Skill zone id

    Returns:
    GET : return Skill zone view template
    """
    try:
        skill_zone = SkillZone.objects.get(id=sz_id)
        is_active = skill_zone.is_active
        if is_active == True:
            skill_zone.is_active = False
            messages.success(request, _("Skill zone archived successfully.."))

        else:
            skill_zone.is_active = True
            messages.success(request, _("Skill zone unarchived successfully.."))

        skill_zone.save()
    except SkillZone.DoesNotExist:
        messages.error(request, _("Skill zone not found."))

    return redirect(skill_zone_view)


@login_required
@manager_can_enter(perm="recruitment.view_skillzone")
def skill_zone_filter(request):
    """
    This method is used to filter and show Skill zone view.
    """
    template = "skill_zone/skill_zone_card.html"
    if request.GET.get("view") == "list":
        template = "skill_zone/skill_zone_list.html"
    skill_zone_filter = SkillZoneFilter(request.GET).qs.filter(is_active=True)
    if request.GET.get("is_active") == "false":
        skill_zone_filter = SkillZoneFilter(request.GET).qs.filter(is_active=False)
    previous_data = request.GET.urlencode()
    data_dict = parse_qs(previous_data)
    get_key_instances(SkillZone, data_dict)
    context = {
        "skill_zones": paginator_qry(skill_zone_filter, request.GET.get("page")),
        "pd": previous_data,
        "filter_dict": data_dict,
    }
    return render(
        request,
        template,
        context,
    )


@login_required
@manager_can_enter(perm="recruitment.view_skillzonecandidate")
def skill_zone_cand_card_view(request, sz_id):
    """
    This method is used to show Skill zone candidates.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone id

    Returns:
    GET : return Skill zone candidate view template
    """
    skill_zone = SkillZone.objects.get(id=sz_id)
    template = "skill_zone_cand/skill_zone_cand_view.html"
    sz_candidates = SkillZoneCandidate.objects.filter(
        skill_zone_id=skill_zone, is_active=True
    )
    context = {
        "sz_candidates": paginator_qry(sz_candidates, request.GET.get("page")),
        "pd": request.GET.urlencode(),
        "sz_id": sz_id,
    }
    return render(request, template, context)


@login_required
@manager_can_enter(perm="recruitment.add_skillzonecandidate")
def skill_zone_candidate_create(request, sz_id):
    """
    This method is used to add candidates to a Skill zone.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone id

    Returns:
    GET : return Skill zone candidate create template
    """
    skill_zone = SkillZone.objects.get(id=sz_id)
    template = "skill_zone_cand/skill_zone_cand_form.html"
    form = SkillZoneCandidateForm(initial={"skill_zone_id": skill_zone})
    if request.method == "POST":
        form = SkillZoneCandidateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Candidate added successfully."))
            return HttpResponse("<script>window.location.reload()</script>")

    return render(request, template, {"form": form, "sz_id": sz_id})


@login_required
@manager_can_enter(perm="recruitment.change_skillzonecandidate")
def skill_zone_cand_edit(request, sz_cand_id):
    """
    This method is used to edit candidates in a Skill zone.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone candidate id

    Returns:
    GET : return Skill zone candidate edit template
    """
    skill_zone_cand = SkillZoneCandidate.objects.filter(id=sz_cand_id).first()
    template = "skill_zone_cand/skill_zone_cand_form.html"
    form = SkillZoneCandidateForm(instance=skill_zone_cand)
    if request.method == "POST":
        form = SkillZoneCandidateForm(request.POST, instance=skill_zone_cand)
        if form.is_valid():
            form.save()
            messages.success(request, _("Candidate edited successfully."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, template, {"form": form, "sz_cand_id": sz_cand_id})


@login_required
@manager_can_enter(perm="recruitment.delete_skillzonecandidate")
def skill_zone_cand_delete(request, sz_cand_id):
    """
    function used to delete Skill zone candidate.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone candidate id

    Returns:
    GET : return Skill zone view template
    """

    try:
        SkillZoneCandidate.objects.get(id=sz_cand_id).delete()
        messages.success(request, _("Skill zone deleted successfully.."))
    except SkillZoneCandidate.DoesNotExist:
        messages.error(request, _("Skill zone not found."))
    except ProtectedError:
        messages.error(request, _("Related entries exists"))
    return redirect(skill_zone_view)


@login_required
@manager_can_enter(perm="recruitment.view_skillzonecandidate")
def skill_zone_cand_filter(request):
    """
    This method is used to filter the skill zone candidates
    """
    template = "skill_zone_cand/skill_zone_cand_card.html"
    if request.GET.get("view") == "list":
        template = "skill_zone_cand/skill_zone_cand_list.html"

    candidates = SkillZoneCandidate.objects.all()
    candidates_filter = SkillZoneCandFilter(request.GET, queryset=candidates).qs
    previous_data = request.GET.urlencode()
    data_dict = parse_qs(previous_data)
    get_key_instances(SkillZoneCandidate, data_dict)
    context = {
        "candidates": paginator_qry(candidates_filter, request.GET.get("page")),
        "pd": previous_data,
        "filter_dict": data_dict,
        "f": SkillZoneCandFilter(),
    }
    return render(
        request,
        template,
        context,
    )


@login_required
@manager_can_enter(perm="recruitment.delete_skillzonecandidate")
def skill_zone_cand_archive(request, sz_cand_id):
    """
    function used to archive or un-archive Skill zone candidate.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone candidate id

    Returns:
    GET : return Skill zone candidate view template
    """
    try:
        skill_zone_cand = SkillZoneCandidate.objects.get(id=sz_cand_id)
        is_active = skill_zone_cand.is_active
        if is_active == True:
            skill_zone_cand.is_active = False
            messages.success(request, _("Candidate archived successfully.."))

        else:
            skill_zone_cand.is_active = True
            messages.success(request, _("Candidate unarchived successfully.."))

        skill_zone_cand.save()
    except SkillZone.DoesNotExist:
        messages.error(request, _("Candidate not found."))
    return redirect(skill_zone_view)


@login_required
@manager_can_enter(perm="recruitment.delete_skillzonecandidate")
def skill_zone_cand_delete(request, sz_cand_id):
    """
    function used to delete Skill zone candidate.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone candidate id

    Returns:
    GET : return Skill zone view template
    """
    try:
        SkillZoneCandidate.objects.get(id=sz_cand_id).delete()
        messages.success(request, _("Candidate deleted successfully.."))
    except SkillZoneCandidate.DoesNotExist:
        messages.error(request, _("Candidate not found."))
    except ProtectedError:
        messages.error(request, _("Related entries exists"))
    return redirect(skill_zone_view)


login_required
manager_can_enter(perm="recruitment.change_candidate")


def to_skill_zone(request, cand_id):
    """
    This method is used to Add candidate into skill zone
    Args:
        cand_id : candidate instance id
    """
    candidate = Candidate.objects.get(id=cand_id)
    template = "skill_zone_cand/to_skill_zone_form.html"
    form = ToSkillZoneForm(initial={"candidate_id": candidate})
    if request.method == "POST":
        form = ToSkillZoneForm(request.POST)
        if form.is_valid():
            skill_zones = form.cleaned_data["skill_zone_ids"]
            for zone in skill_zones:
                if not SkillZoneCandidate.objects.filter(
                    candidate_id=candidate, skill_zone_id=zone
                ).exists():
                    zone_candidate = SkillZoneCandidate()
                    zone_candidate.candidate_id = candidate
                    zone_candidate.skill_zone_id = zone
                    zone.save()
            messages.success(request, "Candidate ")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, template, {"form": form, "cand_id": cand_id})


@login_required
def update_candidate_rating(request, cand_id):
    """
    This method is used to update the candidate rating
    Args:
        id : candidate rating instance id
    """
    cand_id = cand_id
    candidate = Candidate.objects.get(id=cand_id)
    employee_id = request.user.employee_get
    rating = request.POST.get("rating")
    rate = CandidateRating.objects.get(candidate_id=candidate, employee_id=employee_id)
    rate.rating = int(rating)
    rate.save()
    return redirect(recruitment_pipeline)


def open_recruitments(request):
    """
    This method is used to render the open recruitment page
    """
    recruitments = Recruitment.default.filter(closed=False, is_published=True)
    context = {
        "recruitments": recruitments,
    }
    response = render(request, "recruitment/open_recruitments.html", context)
    response["X-Frame-Options"] = "ALLOW-FROM *"

    return response


def recruitment_details(request, id):
    """
    This method is used to render the recruitment details page
    """
    recruitment = Recruitment.default.get(id=id)
    context = {
        "recruitment": recruitment,
    }
    return render(request, "recruitment/recruitment_details.html", context)


@login_required
@manager_can_enter("recruitment.view_candidate")
def get_mail_log(request):
    """
    This method is used to track mails sent along with the status
    """
    candidate_id = request.GET["candidate_id"]
    candidate = Candidate.objects.get(id=candidate_id)
    tracked_mails = EmailLog.objects.filter(to__icontains=candidate.email).order_by(
        "-created_at"
    )
    return render(request, "candidate/mail_log.html", {"tracked_mails": tracked_mails})


@login_required
@permission_required("recruitment.add_recruitmentgeneralsetting")
def candidate_self_tracking(request):
    """
    This method is used to update the recruitment general setting
    """
    settings = RecruitmentGeneralSetting.objects.first()
    settings = settings if settings else RecruitmentGeneralSetting()
    settings.candidate_self_tracking = "candidate_self_tracking" in request.GET.keys()
    settings.save()
    return HttpResponse("success")


@login_required
@permission_required("recruitment.add_recruitmentgeneralsetting")
def candidate_self_tracking_rating_option(request):
    """
    This method is used to enable/disable the selt tracking rating field
    """
    settings = RecruitmentGeneralSetting.objects.first()
    settings = settings if settings else RecruitmentGeneralSetting()
    settings.show_overall_rating = "candidate_self_tracking" in request.GET.keys()
    settings.save()
    return HttpResponse("success")


def candidate_self_status_tracking(request):
    """
    This method is accessed by the candidates
    """
    self_tracking_feature = check_candidate_self_tracking(request)[
        "check_candidate_self_tracking"
    ]
    if self_tracking_feature:
        if request.method == "POST":
            email = request.POST["email"]
            phone = request.POST["phone"]
            candidate = Candidate.objects.filter(
                email=email, mobile=phone, is_active=True
            ).first()
            if candidate:
                return render(
                    request, "candidate/self_tracking.html", {"candidate": candidate}
                )
            messages.info(request, "No matching record")
        return render(request, "candidate/self_login.html")
    return render(request, "404.html")


@login_required
@permission_required("recruitment.view_rejectreason")
def candidate_reject_reasons(request):
    """
    This method is used to view all the reject reasons
    """
    reject_reasons = RejectReason.objects.all()
    return render(
        request, "settings/reject_reasons.html", {"reject_reasons": reject_reasons}
    )


@login_required
@permission_required("recruitment.add_rejectreason")
def create_reject_reason(request):
    """
    This method is used to create/update the reject reasons
    """
    instance_id = eval(str(request.GET.get("instance_id")))
    instance = None
    if instance_id:
        instance = RejectReason.objects.get(id=instance_id)
    form = RejectReasonForm(instance=instance)
    if request.method == "POST":
        form = RejectReasonForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Reject reason saved")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, "settings/reject_reason_form.html", {"form": form})


@login_required
@permission_required("recruitment.delete_rejectreason")
def delete_reject_reason(request):
    """
    This method is used to delete the reject reasons
    """
    ids = request.GET.getlist("ids")
    reasons = RejectReason.objects.filter(id__in=ids)
    for reason in reasons:
        reasons.delete()
        messages.success(request, f"{reason.title} is deleted.")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
